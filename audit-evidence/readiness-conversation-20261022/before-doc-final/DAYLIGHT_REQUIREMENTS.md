# Daylight owner requirements

Updated 2026-10-21. Binding requirements from the owner's review of the current app and their confirmation: **keep the journey and restore the visual guide**.

Read this with `PRODUCT.md` before changing the interface. Keep requirement IDs stable. Add new requirements and record explicit owner revisions; do not silently reinterpret or delete existing ones. Implementation reports, model preferences, tests, and older plans cannot supersede this list.

## Requirements

| ID | Binding requirement | How to verify |
| --- | --- | --- |
| D01 | Keep the step-by-step journey; restore the picture-based guide, diagrams, flow charts, map, and useful teaching content. | Walk the beginner path and inspect the visuals at their teaching steps; compare with earlier captures and the V0–V8 inventory. |
| D02 | Simplifying the interface must not remove useful lessons or factual content. | Review content removed or hidden by the diff; maintain a visual/content inventory. |
| D03 | Use one header sun/logo. Remove the duplicate sun and repeated Daylight Medicare identity from the arrival content. | Inspect the arrival screen. |
| D04 | The tab title is `Daylight`, using the existing sun favicon. | Inspect browser title and favicon. |
| D05 | Make the guided start the clear entry for a first-time user. Identify direct plan comparison as the route for people who already understand their options. | A new visitor can explain the difference between the two routes. |
| D06 | Each guided page has one consistently placed Continue action. Avoid multiple competing primary actions, such as Check location plus Continue. | Inspect every question state before and after answering. |
| D07 | Keep the main question, tappable choices, and Continue near the top. Pair a compact visual explanation beside the task on larger screens and close to the question on phones; deeper explanations follow below. | Verify that both the task and its teaching picture are easy to find on desktop, tablet, and phone. |
| D08 | Back, edit, and help remain visible and text-labeled, with lower emphasis than Continue. Do not use the single Continue rule to remove necessary controls. | Complete the journey, correct an answer, and open/close help using touch and keyboard. |
| D09 | Give elements breathing room. Favor clear separation and readable text over squeezing everything into one viewport. | Inspect the smallest supported viewport and tablet layout for crowding and overlap. |
| D10 | Icons must have visible supporting text. Do not hide necessary actions in gestures, hover states, or unlabeled icons. | Inspect help/close, progress, input, and navigation controls. |
| D11 | Make the full answer choice tappable with clear selected and unselected states. | Tap choice edges and operate them with keyboard; inspect accessible state. |
| D12 | New questions start unanswered. Do not preselect or automatically click an answer; retain only answers the person explicitly entered. | Start fresh, advance through untouched questions, then go back to verify previously entered answers. |
| D13 | Progress must advance naturally with the actual journey, including questions within a stage. Do not mark unknown, skipped, or failed work as complete. | Walk beginner, experienced, unknown-answer, and unavailable-service paths. |
| D14 | State the local 2027 Collier County comparison scope clearly once where relevant; do not repeat the same paragraph across intake pages. | Inspect arrival, recipient, goal, ZIP, and county screens for duplication. |
| D15 | Use literal, short next-action wording. Remove confusing labels such as `Continue to current Medicare status`. | Review every Continue label in context. |
| D16 | Ask for birth information people know directly; never make them calculate the year of their 65th birthday. Keep uncertain/different-eligibility routes available. | Enter a birth month/year and check the derived age-65 timing without mental arithmetic. |
| D17 | Names are optional. No account or mandatory personal identification is introduced. | Complete the guide without giving a name or identifier. |
| D18 | Avoid animation. State changes and progress remain understandable without motion. | Inspect CSS and walkthrough behavior, including reduced motion. |
| D19 | Microcopy is literal, clear, and free of unexplained jargon. Explain unavoidable Medicare terms where introduced. | Read screens as a first-time user; check definition access. |
| D20 | Present information visually through diagrams, grids, and tables where they aid understanding. Avoid replacing pictures with dense prose. | Review coverage lessons, comparisons, dates, and final map. |
| D21 | Preserve the useful adaptive workflow, truthful progress, entered notes, date safeguards, catalog controls, and actionable checklist. | Exercise existing meaningful regression checks alongside visual walkthroughs. |
| D22 | Keep sources and checked/unknown distinctions visible. Do not fabricate costs, provider confirmation, approval, or plan suitability. | Inspect factual displays, missing-data states, and API error paths. |
| D23 | Keep existing backend evidence, validation, privacy, and acceptance safeguards intact while restoring the frontend. | Review scope of the diff and verify failure handling. |
| D24 | Verify the rendered result on desktop, iPad/tablet, and phone before calling a UI change complete. Passing code tests alone does not establish usable design. | Record actual walkthrough evidence and any remaining limits. |
| D25 | Ask Daylight is visibly available on arrival and throughout the journey, below Continue and Back where the person interacts. It opens a real conversation interface and preserves the person's place and answers. Do not duplicate it in the header or at the top of the lesson. | Inspect its position, open chat, close it, and continue the same task. |
| D26 | Balance the guided flow with clear Medicare teaching. Pair each substantive question with a concise relevant visual and an explanation, with deeper material available below. Do not bury the entire teaching guide below a long form. | A first-time user can see how the coverage options fit together while answering, on desktop, tablet, and phone. |
| D27 | Link the visual guide and chat: offer relevant plain-language questions and show the supporting visual in the answer when useful. Keep the existing useful journey flow. | Ask about A/B, the two coverage routes, and prescription coverage; verify the response and diagram match the topic. |
| D28 | Distinguish source-linked guide answers from live generated replies. Common guide explanations remain useful when the live service is unavailable; never pretend that a disconnected service answered a question. | Test ready-made questions, typed basic questions, an unsupported question, and the live-service unavailable state. |
| D29 | Begin the beginner guide with one core concept: what Medicare is. Introduce additional concepts only when relevant, question by question; the visual picture grows cumulatively. Do not show the complete insurance diagram at the beginning. | Walk a fresh beginner session and inspect the first appearance of A/B, prescription coverage, costs, the two routes, and Medigap. |
| D30 | Explain clearly why each personal question matters and connect it to the coverage component currently being taught. Preserve learned concepts as the picture grows. | Check each question's relevance explanation and visual focus; go Back without losing the learned picture or personal answers. |
| D31 | People already familiar with Medicare can skip beginner teaching and compare plans after the necessary location checks. | Follow the experienced route; do not force beginner lessons or mark skipped intake complete. |
| D32 | Retain the warm aesthetic while making the interface feel like a credible, finished service: coherent structure, typography, forms, navigation, and spacing. Do not invent credentials, endorsements, availability, or trust claims. | Inspect the actual desktop, tablet, and phone experience, including chat and service failures. |
| D33 | Common actions and available follow-up questions must be visible. Do not hide them behind chat dropdowns, collapsed disclosure menus, icons, or gestures. | Use chat without opening any collapsed section to discover how to ask another question or return to the guide. |
| D34 | When a question or coverage piece opens chat, show the person's question clearly with its answer. Return to the same guide question, answers, and reading place. | Open help from a named piece and a suggested question on desktop, tablet, and phone; verify the question remains identifiable without searching the transcript. |
| D35 | Keep the current activity clear. The question, learning picture, chat, and follow-up choices must not all compete for attention. Preserve useful learning content while reducing simultaneous presentation. | Review closed-help, open-help, follow-up, and return states for a first-time older user. |
| D36 | Use W3C's older-user guidance and COGA as the accessibility and cognitive-usability baseline for this review and finish work. Validate with older users; a detector result is not usability evidence or WCAG certification. | Map proposed changes to those references and use observed task completion and comprehension in user sessions. |
| D37 | Help uses a focused answer view with an explicit Return to the guide. Implement all four passes of the 65+ finish plan before formative sessions: help, question clarity, final checklist, and verification/polish. | Verify the selected question and direct answer, visible follow-ups, unchanged guide/draft on return, usable controls and checklist, and device/keyboard evidence. Record checks requiring real participants or hardware separately. |
| D38 | Remove the landing-page “A clearer picture, one step at a time” preview, its Medicare tile, and its three explanatory steps. Keep the visual lessons within the guided journey. | Inspect the landing page on desktop, tablet, and phone; confirm the guide still starts with the Medicare lesson. |
| D39 | Organize conservatively without deleting files or data or breaking/changing the current UI. Preserve all original content and unrelated work, archive obsolete proposals with a path/hash ledger and before-images, synthesize current docs, and review representative devices/flows. Do not commit, push, publish, or externally upload this work unless the owner separately authorizes that action and destination. | Compare original hashes against retained locations/before-images; inspect UI/runtime equivalence and diff; report baseline failures and residual gaps honestly. |
| D40 | Center-align the landing-page headline and supporting text, with the entry actions centered beneath them. | Inspect the landing content alignment on desktop, tablet, and phone. |


| D41 | Begin the guided journey with the four goals in the vision guide, then ask who it is for once before personal coverage questions. Tailor learning, browsing, review/change/add, and job-transition routes. Understanding, keeping coverage, comparison, and preparation are valid outcomes. The experienced shortcut bypasses broad goal and full personal intake. | Walk a ZIP-free learning visit, category-and-location browsing, coverage review/change, and direct job-transition support. |
| D42 | Provide visible Show / Hide Medicare guide controls. The shortcut begins collapsed; a manual preference persists through forward, Back, and goal changes in this tab. Keep essential question/relevance/source/help content available. | Hide, advance, go Back, change goal, and verify the guide stays hidden until explicitly shown. |
| D43 | Named picture pieces open explanations within the picture area, preserving active question/answers. Ask Daylight uses a contained desktop dialog and an adaptable phone sheet, with visible Return, Escape, appropriate focus containment/restoration, and retained draft/history/place. | Open a local explanation without disabling the task; open/close chat on desktop/tablet/phone and verify continuity. Refines D27 and D37's presentation. |
| D44 | Identify Daylight visibly as an AI assistant that helps the user remain in control. Distinguish source-linked guide explanations, live AI replies, and unavailable replies. State actual chat transmission/logging behavior near submission. | Inspect first help use, a guide reply, a live/unavailable reply, and the submission disclosure. |
| D45 | Ask “Do you have Medicare yet?” before card guidance. Preserve reported A/B, A only, enrolled/parts unknown, no enrollment, enrollment unsure, and another-situation paths including B only. Card help is optional and conditional; no number/upload. Use the approved plain-language Advantage, supplement bridge, current-coverage, and priority wording. | Check all enrollment states; verify card instructions do not precede enrollment answers, and unknown facts generate no invented dates or parts. |
| D46 | Resolve unique ZIP/county matches from a sourced, dated, refreshable complete crosswalk; ask only for ambiguous/missing/unavailable matches and preserve unsure. Keep catalog boundaries. Valid single-field forms can submit with Enter; answer selection never also advances, notes retain newlines, chat cannot submit the journey. | Verify 34102 against source, multi-county 34134, invalid/unknown/outside ZIP, lookup failure, form validation, composition, notes, and chat. |
| D47 | Comparisons show plan identity/category/year/location, available published facts, missing/conflicting values, and remaining personal checks. Retain candidates/notes on edits but invalidate stale results; current coverage remains a valid baseline to keep, with missing policy facts explicit. Supplement education is not an insurer quote. | Save/compare candidates, change goal/location/coverage, inspect retained candidates and refreshed results; exercise unsupported supplement and failed-service states. |
| D48 | Finish with one relevant next step and useful editable preparation assistance: benefits-office questions, enrollment script, drug-notice request, doctor/medicine checks, supplement questions, or learning/review summary. Provide copy/edit/print and route-aware Back. Prepared is not sent; no outreach or enrollment is promised. Print the same reported facts, unknowns, notes, candidates, scoped actions, drafts, and date. | Exercise direct transition and comparison endings; edit/copy a draft, return, print, and verify parity without duplicate numbering or completed-service claims. |

## Latest agent-first design requirements

These requirements record the latest design direction. They are specified, not yet implemented.

| ID | Binding requirement | How to verify |
| --- | --- | --- |
## Latest agent-first design requirements

These requirements record the latest design direction. They are specified, not yet implemented.

| ID | Binding requirement | How to verify |
| --- | --- | --- |
| D49 | The experience is AI agent first for people comfortable with LLMs: the agent orchestrates contextual teaching, questions, profile and explanations within auditable state/branch rules. Preserve guided visual teaching and explicit controls; do not implement a fixed wizard with a chatbot attached or revive the old all-chat levels flow. | Demonstrate multi-fact entry, contextual next-task proposals and confirmed route changes against the master contract. |
| D50 | Offer voluntary New / Know some / Comfortable knowledge choices plus free text, with confirmed interpretation and per-topic Explain / I know this. Goal is not expertise; seen and self-reported familiarity are not demonstrated understanding. No quiz gate. | Exercise every knowledge choice and ambiguous text; change depth without losing facts or skipping required checks. |
| D51 | Use the same stable common high-level progress phases across routes, with personalized substeps. Do not dynamically renumber phases, mark skipped facts complete or infer mastery. | Compare all goal/knowledge paths, edits and help return; phase IDs/labels/order stay fixed. |
| D52 | Open-ended questions support Something else text. Retain original words, confirm interpretation before using facts, preserve unresolved details, and stay within reviewed deterministic insurance rules. | Confirm/edit/reject multi-fact and ambiguous interpretations; unknowns and original text survive. |
| D53 | Design persistent backend guest profiles without account creation and same-browser resume. This supersedes the old session-only target policy; cross-device/lost-session recovery is separately unresolved and not promised. This documentation does not implement storage. | Before production, verify secure guest authorization, real save receipts, resume/expiry, review/deletion and configured retention policy. |
| D54 | Guest persistence must be explicit and minimal, with plain-language notices, shared-device safety, optional sensitive-field saving, LLM context minimization, logging limits, review and scoped deletion. Backend storage does not silently save everything. Exact retention/vendor/legal policy needs separate review. | Inspect synthetic canaries in requests/storage/logs; separate save/AI/share choices and test profile isolation/deletion/history behavior. |
| D55 | Retain Daylight name/sun and a professional warm aesthetic with meaningful representative people/photography. Grow the beginner picture one concept at a time; knowledgeable users can hide/show it. The finish must address composition and useful imagery, not CSS-only polish. | Inspect concept reveal order and purposeful imagery on desktop/tablet/phone; no fake endorsement, decorative animation or crowded tasks. |
| D56 | Specify an eventual comparison dashboard with consistent dimensions, evidence/unknowns, transparent supported ordering, contextual Ask Daylight, explicit user preference and useful next steps. Personal pricing/provider fit/Medigap quotes and human handoff remain gated by verified capability and actual fulfillment. | Exercise keep/undecided/compare, unsupported/stale/error states and preparation; selection never means sent, enrolled or coverage effective. |
| D57 | Use the master design specification, complete node/answer inventory, branching wireframes and acceptance contract for future work. Record decision changes and affected flow/state before implementation; styling requests cannot silently change product behavior or remove content. | Every scoped implementation names requirement IDs, nodes, state effects, regressions, rendered checks and remaining limits. |

## Latest approved visual/implementation scope

| ID | Binding owner requirement | Acceptance evidence |
|---|---|---|
| D58 | Candidate02 layout and exact Option A (Marcus Aurelius/Pexels6787568) are approved. Follow root DESIGN.md; retain the sole exact tagline Your coverage, plain as day. Do not reopen the layout or add slogans. | Match approved desktop/phone captures; keep asset source/license/crop records. |
| D59 | Implement the first bounded working slice in the active app: goal→recipient as needed→voluntary knowledge/text confirmation→first concepts/growing picture→Ask overlay/exact return. Continue staged implementation without redundant approval; no commit/push/deploy or privacy/data-gate bypass. | Meaningful state/branch tests and actual browser checks; preserve legacy content/routes and uncommitted work. Backend guest saving remains explicitly unconnected until its secure policy/service slice. |

## Interpretation already settled

- Historical restoration direction: **Keep the journey and restore the visual guide.** Latest D49 confirms **AI agent first** within that understandable guided visual experience; the agent orchestrates contextual tasks and teaching. Do not revive either a rigid wizard with bolted-on chat or the superseded all-chat levels implementation.
- One Continue action refers to advancing a guided page. Tappable answers, Back, help, editing, and the actual controls needed to compare plans remain available with clear labels and appropriate emphasis. Nothing in this list authorizes automatic progression after an answer.
- Information may appear below the controls. The breathing-room requirement takes precedence over older proposals to force all content into one viewport.
- The existing tagline is `Your coverage, plain as day`. The owner quoted the previous implementation report to identify the version under review; that quotation does not approve every change in the report.
- Restoration means targeted changes that preserve useful functional fixes. There is no instruction to reset the entire working tree or discard unrelated work.
- **Latest refinement:** build understanding like a newcomer learning a new universe: one concept first, then a cumulative picture. The video-game analogy describes learning pace, not permission for scores, decorative motion, or childish game styling. Place Ask Daylight below Continue and Back. Keep the established warm aesthetic and raise the finish of the service.
- **Chat review:** the owner likes the current appearance and progressive direction. Fix the unclear question on chat opening, remove hidden follow-up menus, and reduce competition between the guide, pictures, choices, and conversation. D27 does not require a diagram in every reply. The owner subsequently approved the focused answer view and the complete staged implementation plan, starting with chat.

## Superseded or conflicting instructions

| Earlier instruction or claim | Current resolution |
| --- | --- |
| Old chat-first levels and late-emerging map | D49: agent-first orchestration with persistent understandable visual teaching and stable progress; no restoration of the old level mechanics. |
| Always keep all explanation within one screen | Give controls breathing room; supporting explanation may follow below. |
| Multiple equally prominent Next / more detail / ask / check actions | One Continue action, with lower-emphasis labeled help and Back. |
| Motion and signature unlock animations | Avoid animation. |
| Pictures/lessons hidden under optional details or removed to simplify flow | Restore visible teaching visuals where they explain the current task. |
| Fixed 94 × 94 tiles as a universal visual requirement | This is an earlier implementation choice, not a binding owner requirement. Usability, text, and spacing win. |
| Passing tests establishes the UI as finished | Verify content retention and the rendered experience on the target devices. |

## Change log

- **2026-10-20:** Created D01–D24 from the owner's review and confirmed restoration direction. Product context recorded in `PRODUCT.md`. Existing briefs preserved as historical evidence; conflicts resolved above.
- **2026-10-20, guide/chat review:** Added D25–D28. Preserve the journey; make the visual guide and contextual Ask Daylight visible and useful together. This refines D07's placement rule; it does not restore a chat-led flow.
- **2026-10-20, progressive-learning review:** Revised D25 placement and added D29–D32. The owner explicitly moved Ask Daylight below the task controls, requested gradual concept teaching beginning with Medicare itself, retained the experienced shortcut, and asked for a more professional finish within the existing aesthetic.
- **2026-10-20, 65+ finish review:** Added D33–D36 from the owner's chat/overload feedback and endorsement of W3C older-user guidance and COGA. Keep the aesthetic and journey. Review and propose the finishing work before changing the UI.

- **2026-10-20, finish implementation approved:** Added D37. The owner selected focused help and authorized all four finish passes, then plans 6–8 formative sessions. Preserve session-only storage and the established appearance.

- **2026-10-20, landing simplification:** Added D38 at the owner’s explicit request. Removed the arrival preview and its supporting copy; consolidated the landing page into a single column.

- **2026-10-21, repository sweep:** Added D39 from the owner’s explicit request to review and organize `/Users/cep4u/daylight` with no deleted files/data and no broken UI. Preserve originals and uncommitted work, archive rather than delete, document current evidence/limits, and leave GitHub commit/push to the owner.

- **2026-10-21, landing alignment:** Added D40 from the owner’s explicit request for centered landing-page text. Centered the headline, supporting copy, entry actions, and help group within the existing single column.

- **2026-10-21, separate GitHub authorization:** The owner subsequently requested a commit and push to `https://github.com/cpuglis1/daylight-medicare.git`. D39’s initial no-publication boundary is superseded for that explicit request. Isolate the cleanup changes, preserve unrelated app/data work and local private/large files, inspect outgoing history and destination visibility, and verify any completed push.

- **2026-10-21, next-iteration review requested:** Captured the owner’s guide-collapse, contained-help, AI-identity, enrollment-question, location, wording, and supportive-checklist feedback in [the next-iteration action guide](docs/DAYLIGHT_NEXT_ITERATION_ACTION_GUIDE.md). The guide distinguishes explicit requests from recommendations on goal-first routing, responsive help, Enter behavior, and a future outreach service. Those product choices await owner review; this documentation step does not implement them or promote tentative ideas into binding requirements.

- **2026-10-21, vision guide implementation authorized:** The owner asked to review and implement `docs/DAYLIGHT_VISION_REVIEW_AND_ACTION_GUIDE.md`. Added D41–D48, approving its goal-first routing, local reference explanations, responsive assistant, native single-field submission, scoped results, and preparation-only service recommendations. Goal comes before D29's beginner lesson; the lesson still begins with Medicare itself. D42 qualifies always-visible teaching; D43 replaces the full-page help presentation while preserving focused answers. D39's repository-organization UI freeze applied to that earlier task, not this explicitly authorized UI implementation. No outbound outreach, enrollment, commit, or publication is authorized by this change.

- **2026-10-21, master-design clarification (documentation only):** Added D49–D57 from the owner’s latest agent-first, voluntary knowledge/free-text, stable-phase, confirmed Something else and backend guest-profile directions and the authorized design safeguards. [Master design](docs/product/MASTER_DESIGN.md) is the implementation-planning entrypoint with branching nodes, wireframes and acceptance. It supersedes conflicting wizard-first/session-only target assumptions while preserving factual/data gates. Backend persistence, AI integration, imagery, dashboard and handoff are specified, not implemented; no UI/app/data changes, outreach, commit or push are authorized by this documentation task.

- **2026-10-21, visual approval and implementation:** Added D58–D59 from explicit owner approval of Candidate02 layout and Option A, followed by authorization to finalize DESIGN.md and implement/verify the first bounded working slice. This supersedes earlier task-specific documentation/UI freezes only within that scope. No commit/push/deploy, real sensitive test data or automatic external outreach is authorized.

## Core completion authorization · October 21, 2026

| ID | Binding owner requirement | Acceptance evidence |
|---|---|---|
| D60 | Finish real live AI orchestration using the configured provider, auditable proposed field updates, reviewed teaching, explicit confirmation and failure-safe streaming/cancel/retry. Manual/local fallback must be clearly identified; do not call it live AI. Reuse existing configuration without exposing or copying secrets. Live paid tests require the agreed budget. | Test grounding, schema rejection, owner/version-bound confirmation, context minimization, cancellation, retries and an authorized real-provider smoke test; report any exact outstanding cost/credential blocker. |
| D61 | Implement real backend guest profiles without signup, same-browser resume, opaque protected sessions, ownership/CSRF/origin/version checks, explicit minimal saving, separate optional sensitive-note choice, review/edit/delete, expiry and honest save states. No raw health-chat logs by default. | Synthetic persistence/restart/isolation/concurrency/expiry/deletion tests and browser save/resume/review. Local development defaults are not production compliance approval. |
| D62 | Add about five actual locally sourced Collier plans only as a visibly labeled, unvalidated sample subset with exact identities, year, source/date/provenance and unknown personal fit. Hold personalized comparisons, ranking and verification behind existing data gates. | Verify every sample against captured CMS rows; no fabricated prices, comprehensive-list claims, eligibility or provider/drug matches. The app shell, education, guest profiles and agent must work independently of plan acceptance. |

- **2026-10-21, core completion authorized:** The owner asked to finish live AI orchestration and account-free backend profiles, hold plan comparison/validation/integration, and import about five real sample records. “Push this to completion” authorizes finishing the application work, not a git push. D60–D62 extend D59 and supersede its temporary unconnected-storage/local-rule-only limit. Preserve the approved D58 composition/photo/tagline and all unrelated work. No commit, push, deployment, new credentials, paid accounts or private patient tests are authorized.

## Local AI activation · October 21, 2026

| ID | Binding owner requirement | Acceptance evidence |
|---|---|---|
| D63 | Enable ordinary local AI with the existing OpenAI configuration under a hard $1 USD/day application-wide cap shared across all guests, persistent reservations across restart/concurrency, no automatic retries, and a visible estimate/held-usage indicator. Preserve privacy choices and held plan comparisons. | Atomic server-side ledger, exact provider input counting, verified default-tier prices, bounded output, fail-closed pricing/count/storage, uncertain-charge retention, UTC reset, synthetic boundary/concurrency/restart tests and one minimal live check. No new credentials, public deployment or git push. |

- **2026-10-21, owner approved local paid operation:** D63 supersedes the earlier test-only activation restriction. The owner explicitly approved $1/day total local use, no automatic retries and a visible usage indicator. Budget day/reset is 00:00 UTC. Previous three synthetic calls count toward October 21. No per-guest allowance or service restart may reset the aggregate cap.

## Independence and completeness · October 21, 2026

| ID | Binding owner requirement | Acceptance evidence |
|---|---|---|
| D64 | Daylight aims for comprehensive and unbiased research. Strictly separate commercial economics from the recommendation engine and AI: compensation, contracts, referral/conversion/LTV and proxies cannot affect eligibility, candidate inclusion, filtering, ranking/ties, personal fit or explanations, or suppress uncompensated options. State actual universe, gaps and unknowns; do not equate impartial treatment of a subset with all-market completeness. Keep economic fulfillment downstream of the user's evidence-based decision. | [PRINCIPLES.md](PRINCIPLES.md) and [independence acceptance](docs/product/INDEPENDENCE_ACCEPTANCE.md): commission counterfactuals, feature/prompt isolation, versioned evidence/reasons, missing-plan reports, uncertainty, conflict disclosure, independent governance and optional context-preserving human support. Specified requirements, not implemented recommendation certification; plan gates remain held. |

- **2026-10-21, owner affirmed independence:** The owner endorsed comprehensive, unbiased Medicare guidance with economics truly separate from recommendation/AI, and requested a durable founder/agent reference. Added PRINCIPLES.md, operational acceptance and read-first pointers. “AI-first Chapter” is the internal thesis; “Medicare expertise without giving up control of the process” is positioning, not another homepage tagline. This documentation change authorizes no app behavior, recommendation release, outbound action, commit or push.

## Focused simplification direction · October 21, 2026

| ID | Binding owner direction | Planning / implementation status |
|---|---|---|
| D65 | Simplify the guided hierarchy to sun/Daylight Medicare → stable track → actual question; move routine utilities/status out of that primary stack. Remove consumer Local AI spend text from both page/chat while retaining the $1/UTC-day aggregate backend cap, persistence and no automatic retries. Use a compact intentional sun-agent Ask launcher, a roomier conversation overlay with concise just-in-time privacy/AI disclosure, core coverage architecture only in the map, and relevant teaching paired with questions to reduce forced definition-only clicks. | Owner approved full implementation (“implement in full”, October 21, 2026). Grouping and combined explicit confirmation are authorized. See [revision](docs/product/UI_SIMPLIFICATION_REVISION.md) and [implementation evidence](docs/product/UI_SIMPLIFICATION_COMPLETION.md); technical verification is distinct from owner acceptance. |

- **2026-10-21, focused revision planning requested:** D65 records the owner's explicit hierarchy, Ask, core-map and click-reduction feedback. Its target removal of consumer spend banners supersedes that presentation clause of D63 only; the financial cap and operational safety remain binding. [The revision proposal](docs/product/UI_SIMPLIFICATION_REVISION.md) preserves approved identity, useful content, explicit unknowns/confirmation, privacy and plan gates. No UI/code/data change, paid model call, commit or push is authorized by this planning request.

- **2026-10-21, D65 implementation approved:** The owner said “implement in full.” Implement the complete scoped revision, including contextual grouped questions, optional saving, compact sun-agent entry, wider overlay and core-only coverage map. This supersedes the preceding planning-only restriction. Retain all backend financial, profile and factual safeguards. No commit, push or public deployment is authorized. See the completion report for measured results and remaining verification limits.

## Ten essential questions · D66 · October 21, 2026

| ID | Binding owner direction | Scope/status |
|---|---|---|
| D66 | Exactly ten essential question screens followed by an editable summary. One route; no branching topic menus, mandatory definitions or automatic skipping. Explain why each question is asked through the guide. Familiarity affects depth, not routing. Unknown/later stays valid. Continue only advances one step; explicit Back/Edit may move backward. AI proposals require confirmation and cannot overwrite confirmed answers or move the user. Preserve later answers on edits and flag dependent assumptions. | Owner initially approved a protected preview and testing, then explicitly authorized saving the current version and implementation through local activation. Contract/evidence linked below. No commit, push or public deployment. |

- The owner reported the Part D “What would help next?” navigation loop and asked to “FORCE 10 ESSENTIAL QUESTIONS.” The later authorization was “yes save current and implement all the way though. i just want to see a final local host link that i can poke through.” D66 supersedes variable topic routing/experienced route skipping and the temporary hold before local activation. It does not weaken D63/D64 or release personalized plan comparisons.
- [Exact screen contract](docs/product/TEN_QUESTION_CONTRACT.md) and [technical evidence/rollback](docs/product/TEN_QUESTION_EVIDENCE.md) distinguish owner direction, implementation checks and remaining real-device/user validation. Existing saved profiles must be kept with an explicit recoverable review path; do not invent a migration.

## Accepted ten-question flow refinements · D67 · October 22, 2026

| ID | Binding owner direction | Scope |
|---|---|---|
| D67 | The owner accepted D66 and requested minor refinements: clear start-month copy with explicit Month/Year selectors, discoverable summary continuation above the review answer list, working Ask Daylight on plan options, and no official Plan Finder promotional CTA there for now. Preserve all ten steps, saved values, privacy, brand and the shared cap. | Use Choose a start month; no exact day or implied eligibility. Preserve ambiguous saved wording without guessing. Keep one primary action. On the summary, See plan options stays above the answer list; question 10 keeps ordinary Continue below its choices. Necessary source/gating disclosures remain. |

- Database-backed search is a **future requirement only**. The target field and dataset behind “this” were not specified; clarify them before choosing or building a search database/integration. No search infrastructure or data work is authorized by this note.
- The owner described the ten-question direction as nearly exactly what they want and no longer a UI blocker for an MVP. This is acceptance of the direction with these refinements, not release of personalized plan validation/integration or a claim that every device/usability check is complete. No paid tests, commit, push or public deployment.

- **D67 owner placement correction · October 22, 2026:** The owner clarified that the top continuation belongs on the Review your answers summary, where it is labeled See plan options. Remove the top Review your answers action from question 10; retain ordinary Continue after the priorities, as on other questions. The ten-question sequence remains unchanged.

## Coverage-guide clarity and personal needs · D68 · October 22, 2026

| ID | Binding owner direction | Verification |
|---|---|---|
| D68 | Clearly identify Original Medicare and Medicare Advantage as the two primary alternatives, with equal prominence from their first introduction. Never show an Original-only route as the sole option. Introduce optional Medigap with its first answer-choice mention, under Original Medicare, not as a third route or Advantage addition. Doctors and medications appear inline in the guide as asked, update with drafts, and remain as reported personal-needs annotations after confirmation. | Q4 shows both A/B coverage paths; Q5 introduces optional separate Part D and Medigap. Q6/Q7 annotations distinguish draft, reported, None, add later and unavailable details; no network/formulary verification implied. Later cost teaching elaborates. Exactly ten steps, unchanged persistence/privacy and budget gates. |

Owner wording: “the two primary choices. Original v. advantage”; “its on the page where medigap is mentioned”; “making this misleading before: like its only one option”; “doctors, drugs, as we ask need to pop up in the guide.” Pop up means visible inline reveal, not another modal or required action. [Implementation evidence](docs/product/GUIDE_CLARITY_EVIDENCE.md).

## Planned readiness component · D69 · October 22, 2026

| ID | Owner direction | Status and verification |
|---|---|---|
| D69 | Design a source-backed readiness check after the ten editable answers and before personalized matching. Reuse confirmed facts; ask only consequential missing details, one short question and one specific why line at a time. Unknown/defer remain valid; no loops or generic second intake. Include federal/Florida nuance, distinct evidence levels and matching readiness by capability. | **Research/specification and isolated wireframe only; no live integration authorized in this task.** Zero-follow-up route valid. The contextual intro is “A few details can change which coverage fits. Let’s check what matters for you.” It explains this step, not a new homepage tagline. |

[Design](docs/product/READINESS_DESIGN.md) · [Triggers](docs/product/READINESS_TRIGGERS.md) · [Primary sources](docs/product/READINESS_SOURCES.md) · [Acceptance](docs/product/READINESS_ACCEPTANCE.md). The owner’s hope that this is the last core intake component does not waive independent plan validation, integrations, privacy/schema review, Medicare/Florida expert review or final application checks.
