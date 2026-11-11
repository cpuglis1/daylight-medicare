# Readiness acceptance scenarios and implementation handoff

Research/design draft · October 22, 2026. These are required future implementation tests, not claims the production engine passes. The isolated wireframe has a deliberately limited synthetic interaction model; measured preview checks are recorded in `READINESS_DELIVERY.md` after execution.

## Priority scenarios

| Case | Input / action | Required outcome |
|---|---|---|
| A01 Ordinary confirmed facts | Person/year/home/A-B/current arrangement and relevant priorities already confirmed through structured intake/Ask | Zero follow-ups. R20 distinguishes sufficient reports from accepted source checks. No repeated baseline questions. |
| A02 Complete facts, current held data | All inputs available; consumer acceptance still pending | Zero data-fixing questions. Hold affected matching, offer labeled samples/optional preparation; no claim completion unlocked ranking. |
| A03 Missing actual enrollment | Q4 Already on Medicare; no explicit A/B statuses | RC04 once. No inference that both parts are active. Unknown holds appropriate eligibility-dependent claims, not all education. |
| A04 Birthday/start ambiguity | Turning 65, requested start differs from actual B, first-day birthday or imprecise dates | Separate actual/requested dates. Ask only needed birth context; hold a boundary calculation if precision insufficient. |
| A05 Current work vs COBRA | Employer name known; current/continuation status unclear | RC09 clarifies; RC11 separates job/active-coverage/continuation dates. Do not wait for COBRA expiry or reuse a drug clock as a Part B clock. |
| A06 Employer-size nuance | Age 65 current group vs under-65 disability vs ESRD/multi-employer | Correct reviewed 20/100 variants only where applicable. ESRD/multi-employer complexity routes to review; no generic headcount-based delay verdict. |
| A07 Retiree/family consequences | Outside MA/PDP considered while family retiree benefits exist | Ask/check consequences once; unchecked status holds recommended change, not basic comparison. Never imply old benefits can be restored. |
| A08 HSA | Contributions reported plus pending/retroactive Medicare | Specific timing review, no account balance request or automated tax instruction. Other comparison capabilities need not be held. |
| A09 Florida under-65 Medigap | Florida, under 65, qualifying disability/ESRD report, B start | State-specific rights candidate and evidence need, not federal-only “cannot buy.” No blanket guarantee/price/policy claim. |
| A10 Florida group loss vs federal event | Group termination date plus possible federal GI event | Keep separate source rules and date units. Expert determines applicability; no “use whichever deadline is later.” |
| A11 Advantage trial history | First MA vs prior Medigap dropped to try MA | Distinct event/history paths; exact dates/policy evidence. “Within a year” alone is not confirmed GI. |
| A12 Existing Medigap replacement | User wants a cheaper supplement | Do not confuse AEP with a universal Medigap issue right; no cancellation on a provisional quote. Underwriting/rights review without diagnosis inventory. |
| A13 Medicaid/Extra Help uncertainty | Program reported without current notice/year or dual category | Do not conflate Medicaid/MSP/SSI/LIS/SNP. No bank/tax collection. Unadjusted cost scenarios labeled, no subsidy eligibility invented. |
| A14 Seasonal residence | Winter ZIP in Collier; permanent home elsewhere | Resolve permanent scope where material; routine/emergency travel distinct. Do not claim Collier enrollment availability from vacation ZIP. |
| A15 Duplicate provider | Same name at multiple offices; no authoritative network feed | User confirms identity/location. Missing source remains a system hold, never “out of network” or a negative ranking score. |
| A16 Drug ambiguity | Similar name, unknown strength/form, no pharmacy/quantity | Preserve wording; confirm exact identity before match; quantity/supply/pharmacy only for price. No brand/form substitution or fabricated cost. |
| A17 Part B/restrictions | Clinic-administered drug, prior approval or PA/ST/QL source flag | Differentiate identity, benefit part and restriction approval. Do not promise a prior authorization transfers or classify unsupported costing as no coverage. |
| A18 VA/TRICARE | Combined Q5 military label | Clarify program. No generic stop-B/start-D recommendation; qualified program review if needed. |
| A19 Caregiver | Adult child mixes own prescriptions with parent’s coverage | Keep one subject; research permission separate from protected account authorization. No external transmission or application without separately authorized process. |
| A20 Contradiction | Original arrangement and MA same-period reports, or extracted dates conflict | RC28 explicit resolution. A+B benefits plus MA card is not intrinsically a conflict. Keep superseded history and affected assumptions. |
| A21 All unknown/defer | Every displayed detail answered Not sure or Check later | Each instance consumed once; dependent unknown branches blocked; terminal R20. No automatic second pass or repeated deferred questions on resume. |
| A22 Edit invalidation | Change job loss date, home or drug identity after summary | Preserve other answers; mark dependent checks stale; explicit Review affected checks only. Unchanged deferrals do not reopen automatically. |
| A23 Stale/future-year sources | 2026 rates with 2027 requested, wrong county, missing named review, API timeout | Hold exact capabilities; preserve facts. Never substitute another year or imply a URL visit is verification. |
| A24 AI unavailable/budget exhausted | Parser timeout/offline/cap reached | Structured/manual controls work; free text remains local/unresolved; reviewed local help; no fake response, automatic retry or cap bypass. |
| A25 Late model answer/cancel | User edits/back/defer while a response is in flight | Version/run/instance/request mismatch discards proposal. No state overwrite, route change or optimistic independent verification. |
| A26 Finite burden | Large list, repeated equivalent mentions, cyclic callback attempt | Deduplicate by stable key; six proposed primary prompts at most per explicit pass; one clarification attempt per instance; pending remainder explicit, not silently “complete.” |
| A27 Priority mismatch | Doctor is essential, but one candidate has missing network evidence | No “best match” based on a partial weighted score. Present evidence uncertainty, comparable dimensions and actual universe coverage. |
| A28 Economics perturbation | Change commissions/carrier appointment/referral/estimated LTV only | Queue, explanations, inclusion, capability results and recommendation outputs unchanged. Commercial metadata absent from model/predicate features and training outcome labels. |
| A29 Human help | User requests help or encounters a material unsupported rule | Explain specific reason, offer optional official/qualified help and user-reviewed summary. No forced sales call or claim transfer occurred. |
| A30 Final action | A plan is chosen after source-reviewed comparison | Separate RC30 application/eligibility/transition checks and action approval. Readiness completion alone never enrolls or cancels. |

## Interaction, accessibility and safety checks

- Exactly one primary continuation per question. One concise question and one specific why line; short optional help links, no repeated legal paragraphs. No quiz, auto-advance, unexplained numbering or moving high-level track.
- Every structured answer, free text, Not sure, Check later, Something else, Back, Finish, Edit, Ask, error and retry/cancel state has a terminal or explicit user-controlled return. Unknown and defer are not No; skipped/not asked are distinct from both.
- Keyboard Tab/Shift-Tab order follows the visible task. Selection state is announced; fields have persistent labels/instructions. Focus moves to the new task heading on deliberate navigation. Validation keeps the draft and focuses the error/field without erasing information.
- Help dialog traps focus, Escape/Return closes, restores launcher/input focus and scroll, retains local help draft. Underlying task layout does not reflow. No main-task state or queue mutation from asking for an explanation.
- Desktop, tablet, phone, short-height, 200% zoom/reflow, long free text/names and soft keyboard: controls are reachable, no horizontal overflow, sources optional, diagram relationships still explicit. Real screen-reader speech and varied cognitive-needs comprehension/recovery require participant/device testing, not a certification claim.
- No real guest data in tests. Dedicated private fixture database/cookie for persistence, concurrency, separate guest isolation, consent/redaction/delete and restart. Do not test deletion against real records. Rejected versions remain recoverable, with no silent schema migration.
- No untrusted provider/drug/source/free-text content can inject instructions or set eligibility/verified fields. Schema allowlists, length limits, escaping, source receipts and atomic confirmation must be tested at server boundaries.

## What the prototype proves vs future engine work

The preview demonstrates six scenarios, structured replies, explicit free-text sample confirmation/unresolved fallback, defer/unknown/back/finish, affected-check edit notice, help exact return and capability-specific held boundaries. Its local queue is a deterministic **synthetic simulator**, not an executable Medicare rule pack. It makes no model/API calls or browser storage writes. A sample text interpretation is explicitly scripted; arbitrary text is not passed off as interpreted.

Node tests for this simulator check finite termination, deduplication, dependency suppression, Back without duplicate appends, zero prompts, six-prompt bound and explicit dispositions. These do not validate federal/Florida legal applicability, coverage accuracy, live models, actual guest storage or a recommendation algorithm. Future engine/release tests above remain required and must name rule/code/data receipts. The default app is not integrated by this delivery.
