# Ten essential questions: D66 flow contract

October 21, 2026 · Owner authorized implementation through local activation. This contract replaces variable topic-menu routing for the new default; it does not release personalized recommendations. The old route is preserved for existing guides and rollback.

## Binding route and invariants

`Arrival → T01 → T02 → T03 → T04 → T05 → T06 → T07 → T08 → T09 → T10 → T11 summary → SAMPLE (optional)`.

Exactly ten question screens for every goal/familiarity combination. Continue records the current answer and advances exactly one question. No automatic skipping, topic menus, lesson-only pages, inference of expertise or AI routing. Unknown/add-later answers are valid and unresolved. The four common phases stay fixed; Question n of 10 has a fixed denominator. Answer choices do not advance. Earlier steps remain reachable by sequential Back and explicit summary Edit.

The owner superseded the pre-activation preview hold with “yes save current and implement all the way though. i just want to see a final local host link that i can poke through.” The phased preview/test protection is retained, followed by local activation only. No commit, push or public deployment.

## Screen contracts

### 1. T01 · What would you like help with today?

- Purpose/why: Your goal tells Daylight what to explain and what to emphasize. We will work through your situation, needs and priorities in ten questions.
- Guide: Medicare is federal health insurance that helps pay for health care. We will build the coverage picture as each part becomes relevant.
- Answers: Understand Medicare; Find coverage; Review existing coverage; Something else
- Writes: `intent.goal`, `intent.goalDetail`. Confirmed reports/explicit unknowns only. No independent insurance verification.
- Continue: T02; Back: arrival. Summary-edit Save returns directly to T11; Cancel changes no answer.
- Validation: Something else retains optional wording; an unresolved goal is not an invented insurance route.

### 2. T02 · How familiar are you with Medicare?

- Purpose/why: This sets how much explanation you see. It changes the detail, not the questions or the facts we need.
- Guide: The coverage map will grow one piece at a time. You can hide it and reopen it whenever you want.
- Answers: New to Medicare; Know a little; Comfortable with the basics; Not sure yet
- Writes: `knowledge.general`. Confirmed reports/explicit unknowns only. No independent insurance verification.
- Continue: T03; Back: T01. Summary-edit Save returns directly to T11; Cancel changes no answer.
- Validation: No quiz. Not sure yet preserves the global unknown-answer requirement. Familiarity affects explanation detail/map presentation only.

### 3. T03 · What ZIP code do you live in?

- Purpose/why: Plan availability and published prices can depend on the county. A ZIP lookup is a location reference, not proof of residency.
- Guide: Use the home location of the person whose coverage you are researching. An unknown location stays open for checking.
- Answers: Five-digit home ZIP or Not sure; inline county choice/unknown for ambiguous ZIPs.
- Writes: `comparison.scope.zip`, `comparison.scope.county`, `comparison.scope.locationEvidence`. Confirmed reports/explicit unknowns only. No independent insurance verification.
- Continue: T04; Back: T02. Summary-edit Save returns directly to T11; Cancel changes no answer.
- Validation: Do not derive county from a multi-county ZIP. Unique published lookup is derived, not verified residency. Unknown ZIP clears active county evidence.

### 4. T04 · When do you need Medicare coverage to start?

- Purpose/why: The timing helps organize what to check next. Your requested month does not establish eligibility or an enrollment deadline.
- Guide: Part A covers hospital care and Part B covers medical care. You can receive these benefits through Original Medicare or Medicare Advantage (Part C). Your requested start is not verified eligibility or enrollment.
- Answers: Choose a start month; Already on Medicare; Not sure
- Writes: `coverage.requestedStart`, `coverage.requestedStartMonth`. Confirmed reports/explicit unknowns only. No independent insurance verification.
- Continue: T05; Back: T03. Summary-edit Save returns directly to T11; Cancel changes no answer.
- Validation: A requested month uses separately labeled Month and Year selectors with blank new selections, retained saved years, and internal YYYY-MM storage. Unknown saved wording stays intact and can be explicitly kept without interpretation. No exact day is requested. Already on Medicare is a timing report, not a verified enrollment determination. Store the optional date separately from the timing mode.

### 5. T05 · What health coverage do you have now?

- Purpose/why: We need to understand what is already in place before considering a change. Your answers describe your coverage; they do not verify its benefits.
- Guide: There are two main ways to get Medicare coverage: Original Medicare and Medicare Advantage (Part C). Medigap is optional extra insurance that helps pay your share of Original Medicare costs; it does not work with Advantage. A separate drug plan is Part D; most Advantage plans include it.
- Answers: Original Medicare (Parts A and B); Medicare Advantage (Part C); Medicare Supplement / Medigap; Separate prescription drug plan; Current-job coverage; Retiree coverage; COBRA; VA, TRICARE or military coverage; Medicaid; None; Not sure
- Writes: `coverage.current`. Confirmed reports/explicit unknowns only. No independent insurance verification.
- Continue: T06; Back: T04. Summary-edit Save returns directly to T11; Cancel changes no answer.
- Validation: Multi-select; None and Not sure are exclusive. Contradictory Original/Advantage reports stay visible for review, never auto-corrected.

### 6. T06 · Which doctors or hospitals would you like to keep?

- Purpose/why: Provider access is an important check before choosing coverage. A name alone does not establish participation or guarantee access.
- Guide: We will keep these names as items to verify. No provider network check is connected yet.
- Answers: Add doctors or hospitals; None to check; Add later
- Writes: `needs.providersStatus`, `needs.providers`. Confirmed reports/explicit unknowns only. No independent insurance verification.
- Continue: T07; Back: T05. Summary-edit Save returns directly to T11; Cancel changes no answer.
- Validation: A name is required only after Add is selected; None to check/Add later require no names. Optional names are sensitive notes.

### 7. T07 · What prescriptions do you take?

- Purpose/why: Drug coverage and costs depend on the exact medicine and plan. Dose and pharmacy details can help later; unknown details can stay open.
- Guide: Part D is prescription drug coverage. It is a separate plan with Original Medicare; most Medicare Advantage plans include it. Exact plan rules still need checking.
- Answers: Add prescriptions; None; Add later
- Writes: `needs.medicinesStatus`, `needs.medications`, `needs.medicationDetails`, `needs.pharmacies`. Confirmed reports/explicit unknowns only. No independent insurance verification.
- Continue: T08; Back: T06. Summary-edit Save returns directly to T11; Cancel changes no answer.
- Validation: A medicine name is required only after Add is selected. Dose and pharmacy may be blank. None/Add later require no list; no match/coverage/cost is inferred.

### 8. T08 · Will you need routine care away from home?

- Purpose/why: Routine care away from home can have different coverage limits from emergency care. Tell us where you expect to need routine care.
- Guide: Travel needs become a check on the exact coverage. Do not assume that emergency coverage means routine care is covered.
- Answers: Local only; Another state; Outside the US; Not sure
- Writes: `needs.travel`. Confirmed reports/explicit unknowns only. No independent insurance verification.
- Continue: T09; Back: T07. Summary-edit Save returns directly to T11; Cancel changes no answer.
- Validation: Another state and Outside US may coexist. Local only and Not sure are each exclusive. Routine and emergency coverage are distinct.

### 9. T09 · How would you prefer to balance monthly payments and costs when you get care?

- Purpose/why: This helps us explain the tradeoffs you care about. It is not enough by itself to choose a coverage route or calculate your total costs.
- Guide: Premiums are monthly payments. Deductibles, copays and coinsurance are costs when you get care. Medigap can help with certain Original Medicare costs; it does not pair with Medicare Advantage.
- Answers: Lower monthly payments; More predictable costs; No preference yet
- Writes: `needs.costPreference`. Confirmed reports/explicit unknowns only. No independent insurance verification.
- Continue: T10; Back: T08. Summary-edit Save returns directly to T11; Cancel changes no answer.
- Validation: Preference does not select or rank a route. No preference yet is a reported lack of preference, distinct from missing data.

### 10. T10 · What matters most when we compare your options?

- Purpose/why: Your priorities should guide the comparison, independently of commissions or other commercial relationships. Choose up to three.
- Guide: The map now shows the core arrangements. Personal fit, prices, doctor access and drug coverage remain unverified until the relevant sources are connected.
- Answers: Doctors and hospitals; Prescriptions; Total cost; Predictable costs; Travel; Something else; Not sure
- Writes: `needs.priorities`, `needs.priorityOther`. Confirmed reports/explicit unknowns only. No independent insurance verification.
- Continue: T11 summary; Back: T09. Summary-edit Save returns directly to T11; Cancel changes no answer.
- Validation: At most three priorities. Not sure is exclusive. Other wording is optional and retained as unresolved if blank.

## State, editing and AI boundaries

Use the existing typed schema-2 envelope and versioned guest API, with T01–T11 identifiers. The ten-question route has a separate cookie and private database. Old fields and old profiles are never silently converted, overwritten or deleted. A non-T legacy location fails safe and offers the preserved previous guide. Compatible ten-question state resumes at its exact stored step, with prefilled confirmed answers; Continue still advances only one step. Visiting a concept is not comprehension or enrollment.

Back keeps every later answer/draft. Summary Edit changes only the selected question's fields, returns on explicit Save, and retains later answers while flagging dependent assumptions for review. None/unknown choices deactivate, rather than silently use, retained optional notes. The summary exposes unrecorded/unsaved details, reported coverage conflicts and outstanding checks. It does not imply personalized fit.

AI uses the existing grounded service and shared budget. Only reviewed source facts can explain insurance rules; model output proposes allowlisted reports. Only a supported current-question draft can be filled after confirmation. Confirmed answers cannot be overwritten by AI. No proposal, response, source text or suggested node moves the user. Continue is still required. Sensitive lists/dates are not automatically attached; first transfer requires permission. Mock fixtures are labeled and never call the provider.

## Coverage map and component boundaries

Retain the approved hero/photo, sole tagline, sun/name, fonts, palette, buttons and overlay. New navigation lives in `cms-slice/apps/ten-question/ten-state.js` and `ten-app.js`, with a small scoped stylesheet. Existing `apps/chat` is preserved byte-for-byte for previous-guide review/rollback. Do not edit its topic resolver to implement this route.

Q2 introduces Medicare/outline; Q3 adds location context; Q4 introduces Original Medicare and Medicare Advantage together as the two ways to receive A/B benefits; Q5 adds optional separate Part D and Medigap under Original, with usually-included D under Advantage. Q6 reveals Your doctors and Q7 Your medications as personal annotations. Q7/Q9 elaborate drug/cost checks rather than delaying first-use definitions. Only Medicare/A/B/C/D/Medigap are coverage blocks. Provider, medicine, timing, travel and cost facts are contextual text/annotations, not new coverage nodes. No Medigap+C or universal C+standalone D implication.

On desktop one question is left and relevant why/teaching/map is right. Phone puts the concise explanation near the question and the full map after task controls so it cannot block the answer. Show/Hide remains explicit. Comfortable depth keeps a shorter essential explanation and optional Explain more, not different questions.

## Summary and plan boundary

D67, as corrected by the owner, keeps ordinary Continue below question 10's priority choices; there is no top Review your answers action on that question. T11 keeps See plan options above all ten numbered answer groups and explicit Edit, with one primary continuation. See plan options opens the existing five source-labeled sample records directly; there is no second questionnaire or fabricated personalized result. Exact source IDs/year/date remain. Price/provider/drug fit are unknown, ranking unavailable and plan validation/integration held. Plan options includes the working sun-agent Ask overlay; its context identifies these as unvalidated samples and preserves the current position/draft. The promotional official Plan Finder CTA is removed from this page for now; CMS provenance remains.

## Privacy, recovery and activation

Explicit saving, separate optional wording/date/health-note saving, status/receipts, CSRF/origin/ownership/version checks, expiry, review and scoped delete remain. Chat, original submitted text and unsent drafts are not persisted. Unsaved refresh may lose tab-only work; save explicitly to resume. Dates/notes omitted by consent remain visibly unrecorded rather than guessed. A save conflict preserves the current tab and offers read-only review/load or continuing without saving; no automatic overwrite/merge.

Both local surfaces share the original persistent aggregate $1 per UTC day ledger and no automatic retries. Main ten-question profiles use `var/ten-question-profiles`, cookie `daylight_ten_dev`. Previous profiles remain `var/guest-profiles`, cookie `daylight_guest_dev`, available on port 8896. Fixture port 8894 has its own database/cookie and mock AI; it does not load credentials or use the real budget ledger.

Runtime: `python3 cms-slice/scripts/ten_server.py --port 8890`. Previous guide: same command with `--legacy --port 8896`. Rollback: stop only the recorded ten-question process on 8890; run the preserved original `guide_server.py --port 8890 --model-env .env --enable-live`, or run `ten_server.py --legacy --port 8890`. No database migration, deletion or reset is required. Keep the ten-question database for later recovery; switching ports does not erase either guide.

## Acceptance and evidence

Require T01…T10 exactly once then terminal summary for all four goals × three stated familiarity choices, plus unknown familiarity. Cover unknown/free text, atomic validation, sequential Back, summary edit, AI non-overwrite/no-navigation, consent/minimal context, Ask focus/draft/scroll return, save/resume/isolation/conflict and legacy recovery. Test the Part D cycle as a regression risk; real browser walks must reach summary and sample boundary. Desktop/tablet/phone and short-height/keyboard mechanics need evidence, not just a test count.

See [completion evidence](TEN_QUESTION_EVIDENCE.md). Technical checks are not owner acceptance, screen-reader speech verification or older-adult comprehension testing.

## Future search requirement · D67

The owner wants database-backed search eventually. The referenced field and dataset were ambiguous; neither a concrete search scope nor a database/integration has been approved. Clarify before future implementation. This revision adds no search service or data work. See [refinement evidence](TEN_QUESTION_REFINEMENTS.md).

## D68 visual teaching refinement

Q4 introduces both primary routes together, titled **Two main ways to get Medicare coverage**: Original Medicare A/B and Medicare Advantage Part C providing A/B benefits. Before Q4 only the general Medicare block is shown. Q5 introduces separate Part D and optional Medigap under Original Medicare, synchronized to their answer choices; Advantage usually includes D and never takes a Medigap add-on. Q7/Q9 elaborate drugs/costs. Q6 reveals **Your doctors**, Q7 **Your medications**, inline and separate from coverage blocks. Current drafts are labeled unconfirmed and update without moving focus; confirmed reports survive later steps and hydrated resume, respecting note-saving consent. None/add later/missing saved details do not mean verified participation or coverage. Sequence, answer values, confirmation, Back/Edit and persistence contracts stay unchanged. [Evidence](GUIDE_CLARITY_EVIDENCE.md).
