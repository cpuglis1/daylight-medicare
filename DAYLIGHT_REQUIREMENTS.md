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

## Interpretation already settled

- The owner's answer to the restoration question was: **Keep the journey and restore the visual guide.** Do not reopen chat-first versus journey-first by default.
- One Continue action refers to advancing a guided page. Tappable answers, Back, help, editing, and the actual controls needed to compare plans remain available with clear labels and appropriate emphasis. Nothing in this list authorizes automatic progression after an answer.
- Information may appear below the controls. The breathing-room requirement takes precedence over older proposals to force all content into one viewport.
- The existing tagline is `Your coverage, plain as day`. The owner quoted the previous implementation report to identify the version under review; that quotation does not approve every change in the report.
- Restoration means targeted changes that preserve useful functional fixes. There is no instruction to reset the entire working tree or discard unrelated work.
- **Latest refinement:** build understanding like a newcomer learning a new universe: one concept first, then a cumulative picture. The video-game analogy describes learning pace, not permission for scores, decorative motion, or childish game styling. Place Ask Daylight below Continue and Back. Keep the established warm aesthetic and raise the finish of the service.
- **Chat review:** the owner likes the current appearance and progressive direction. Fix the unclear question on chat opening, remove hidden follow-up menus, and reduce competition between the guide, pictures, choices, and conversation. D27 does not require a diagram in every reply. The owner subsequently approved the focused answer view and the complete staged implementation plan, starting with chat.

## Superseded or conflicting instructions

| Earlier instruction or claim | Current resolution |
| --- | --- |
| Chat-first arrival; reveal the map only at later levels | Keep the journey with an understandable visual guide and progress. |
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
