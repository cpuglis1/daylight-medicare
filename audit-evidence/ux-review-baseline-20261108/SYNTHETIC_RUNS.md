# Three fictional profiles through :8894 → :8893 · November 8, 2026

Owner-authorized live run (chat, Nov 8). Model: gpt-5.4 via OpenAI, local
server without `--pilot`. Budget before: $0.868 / 20 requests; after: $1.540 /
44 requests (≈ $0.67 for 10 user turns, ≈ 6.7¢ per turn including two failed
compositions). Personas are fictional. No app files changed.

## Rosa · 64, turning 65 Feb 2027, working, hospital-system employer, Naples 34102
1. "I turn 65 in February and I'm still working… good insurance through my job… where to start" →
   Reply: job coverage matters, employer size matters, "ask your benefits administrator".
   Question: "Would you like help putting together a short list of questions for your benefits administrator?" (offer, free text, no choices)
2. "I guess so. Big company… few thousand people. Naples 34102." →
   Reply: 3-question list for the benefits administrator. Question: RC10 "Can you confirm the employer has 20 or more employees…" with choices. ZIP captured silently (confirmed later on Plans page).
3. [20 or more] → Reply: script to read to Social Security. Question: "Would you like help preparing for that conversation with Social Security?"
4. "I don't want to call Social Security. Plain words, do I need to sign up in February or not?" →
   **No reply.** Status: "The AI reply could not be checked. You can continue from here."
   errors.log: `unsupported_finding` ×2 (one recovery), then `unavailable question_available=False`. Two paid compositions, nothing shown. Progress track jumped to "Coverage options".
5. "My friend has an Advantage plan and says it's free. What's the difference?" →
   **No reply.** Status: "The AI reply reached its length limit. Your reported details are kept." errors.log: `unavailable`.
6. "What's the difference between Medicare Advantage and Original Medicare?" →
   Good two-path explanation; handled "free" misconception. No inline coverage-path visual. Question: "Would it help to look more closely at how the costs differ?" Sources: one Medicare.gov link.
Plans tab: 72 Medicare Advantage plans, 39 "most people can join", $0 premiums, "Check plans for me" → 11-question modal. Medigap and Part D "Coming soon". Nothing asked about her drugs, doctors, HSA (RC14), husband's coverage, or her priorities (T10) across six turns.

## Frank · 66, Humana MA for ~1 year, winters in Michigan, Marco Island 34145
1. Opening (switch to a supplement?) → Reply: Medigap explained; "check your right to enroll"; "I can't confirm participation or your enrollment rights here." Question: T06 doctors (good, consequential, with choices).
2. "Dr. Patel, cardiology, NCH… rheumatologist at Munson… does it matter I've only been on Advantage a year? Someone said there's a window." →
   Reply: noted both doctors; explained the 6-month Medigap open enrollment (does not apply to a 66-year-old a year past Part B); "other protections may apply". Did not ask RC16 (first MA plan / start / prior Medigap) or RC05 (Part B start), which would have resolved the question. Question: "Would you like help putting together the questions to ask about your Medigap switching rights?"
3. "Yes please. Eliquis and metformin. Marco Island 34145." → Reply: 4-question script for an outside party. Medicines and ZIP taken without acknowledgment. Question: "Would it help to explain what medical underwriting means…"
No "Review your info" offered after three turns (year not known).

## Linda for her mother Dottie · 78, Original Medicare, no Part D, new Jardiance $600/mo, Immokalee 34142
1. Opening → Reply: "ask her pharmacist and prescribing office"; "I can't confirm her price, assistance eligibility or enrollment date here." Question text: "do you mean Original Medicare—Parts A and B—with no separate drug plan, or other coverage too?" Choices rendered: T05 family list (Through a current job / From a former job / Medicare / VA… / Medicaid / No health insurance / I don't know / Check later) — question and choices do not match.
2. [Medicare → Original Medicare (Parts A and B)] → Reply: two-sentence acknowledgment. Refinement label said "Which Medicare coverage do **you** have?" for a caregiver session. Question: ZIP.
3. "34142. Will she get a penalty for not having a drug plan? Is there help for people on a fixed income?" →
   Reply: "I can't determine here whether your mother owes a late-enrollment penalty or qualifies for financial assistance"; script to read to Medicare; one useful sentence (can add Part D without switching to MA). Did not state the general Part D late-enrollment rule or that Extra Help exists; did not ask RC18. Question: "Would you like help putting together a short checklist for that conversation with Medicare?"
Plans tab for this session: Medicare Advantage list; Part D "Coming soon"; card shows "Your prescription: not checked yet" (Jardiance captured).

## Pattern across all ten turns
- 7 of 10 follow-up questions were yes/no offers of the form "Would you like help putting together…" (a list/script for an outside party). 3 were approved meanings with choices (RC10, T06, T03/ZIP) — those were the best turns.
- 0 turns asked about priorities (T10), cost preference (T09), travel (T08) or assistance (RC18).
- 2 of 10 turns produced no visible reply (validation reject; length limit), both on the person's central question.
- General rules the reviewed evidence allows (20+ employer → Part B can be delayed with an SEP; MA trial right in the first 12 months; Part D penalty for months without creditable coverage; Extra Help) were replaced by referrals to outside parties.

---

# Rerun after D109 · November 8, 2026, 12:34–12:40 ET

Same three openings, same local server (gpt-6.1-sol default route), after the
D109 patches and two service restarts. Budget: $1.540 → $1.997 for 7 user
turns and one blanked first attempt (≈ 5.7¢ per turn; no repair cycles after
the spouse-job fix). Pane was 800×600 this time.

## Rosa
1. Opening → **Rule stated**: "With coverage through a current job at an employer with 20 or more employees, people can usually delay Part B without a late-enrollment penalty"; eight-month window after the coverage ends; personal gap named ("the key detail still needed… is your employer's size"). Question: ZIP (approved). *(First attempt before the spouse-job fix: reply dropped by `missing_worker_reference`, question retained — fixed, see below.)*
2. "34102… big hospital system… do I need to sign up in February or not?" → "Noted: Naples, 34102, and coverage through a large employer." Rule applied; Part A premium-free, HSA stops, backdating; "any actual Medicare effective date still needs confirmation through Social Security" as the confirming step. Question: T06 doctors. **This is the turn that produced no reply this morning.**
3. "My friend has an Advantage plan and says it's free…" → "Free" explained, two paths, Medigap/MA rule; returns to the pending T06. **This is the turn that hit the length limit this morning.**

## Frank
1. Opening → Original Medicare nationwide vs. MA networks; Medigap explained; **trial right stated** ("joined Medicare Advantage when first eligible at 65 and leaves within the first 12 months… guaranteed"); six-month period; personal gap ("turns on the first-plan history and exact start dates"). Question: ZIP.
2. ZIP, first plan since last October, Dr. Patel, Eliquis/metformin → all four captures acknowledged in one sentence; access check explained by path. Question: **T10 what matters most** (never asked this morning).
   Limit observed: "joined last October" (12 months ending October 2026) was not connected to the trial right's 12-month clock — that would be a personal date, which the validator blocks by design. Licensed review is where that lands.

## Linda (for her mother)
1. Opening → **Extra Help first** (what it pays, automatic qualifiers, apply through Social Security); Original Medicare can add a stand-alone Part D plan; **Open Enrollment is open now, Oct 15–Dec 7, changes Jan 1**; the 63-day / ~1%-per-month penalty rule; Extra Help removes the penalty. Question: T05 worded as the picker's own question ("What other health coverage, if any, does she have…") with the family list — **no more yes/no sentence over a multiple-choice list**.
Plans tab: opens on "Two ways to get Medicare" with "What you've told us: 1 medicine added."

## Scorecard (7 turns)
- Third-party referrals as the follow-up question: **0 of 7** (was 7 of 10).
- Blank or truncated turns: **0 of 7** (was 2 of 10).
- Approved meaning asked with choices: 7 of 7.
- Rules stated that this morning's run deflected on: working-coverage SEP, Part A/HSA, MA trial right, Original nationwide, Part D penalty, Extra Help, Open Enrollment.

## Fixes made during the rerun
- `natural_agent.py`: the spouse-job assertion check matched "my husband says… my job" and dropped the whole reply; narrowed to assertions about the spouse's own employment/insurance.
- `natural_flow.py`: when validation drops the prose and retains only the question, the reviewed statement fills the reply (floor applied to retained components, not to deliberate question-only replies).
- `applicable_rules.py`: the working-coverage rule lists RC09 as a confirm target when RC10 is not yet askable.

## Still to tune (not blockers)
- RC16 (first MA plan / start) was not in the candidate set for Frank, so the rule's confirm question fell through to ZIP; check RC16 eligibility when coverage includes Advantage and the concern is switching.
- HSA statement appears for every working person approaching 65; consider gating on an HSA mention or RC14.

---

# Second set · November 8, 2026, 13:00–13:30 ET · three new profiles

Owner asked for entirely different profiles: one very direct, one very tricky.
Rules accepted by the owner at 12:48 ("approved"). Two rule gaps found and
added during the set (COBRA, Medigap-return); both openings replayed after a
restart. Turn count: 9 (plus 2 replays).

## Hank · 65, retired Sept 30, COBRA ends Dec 31, Naples 34108, "just tell me which plan to buy"
- Before the COBRA rule: brief, honest ("I don't yet have a supported personal recommendation"), asked doctors; **missed the urgent point** that COBRA does not protect Part B timing. Turn 2 ("just give me the cheapest, my buddy pays zero"): "I don't have a supported comparison identifying the cheapest plan for you, so I won't guess"; zero-premium ≠ free; asked travel. Still no COBRA warning.
- **After the rule (replay):** "With COBRA, Part B timing comes before picking a plan: COBRA isn't coverage based on current employment and doesn't extend the time to sign up for Part B. Waiting for COBRA to end can therefore cause problems. The key missing detail is which Medicare parts you already have." Question: RC04 with choices. [Neither] → "confirm the enrollment route and coverage start date with Social Security" as the confirming step, then doctors.
- Tone held: two sentences of substance, no lecture, no "would you like help preparing…".

## Gloria · 64, Medicare since 2022 by disability, Medicaid, insulin, turning 65 in March, TV grocery-card plan, refused a supplement years ago
- Turn 1 (~50 s): Medicaid → automatic Extra Help; Medicare Savings Programs; would not confirm eligibility for the advertised card ("exact plan's terms and enrollment requirements still need checking"); past refusal: "the federal six-month Medigap period depends on both reaching 65 and being enrolled in Part B… the denial depends on the rights in effect at that time." Question: ZIP.
- Turn 2 ("should I drop Medicaid like the TV guy said?"): **"Don't drop Medicaid based on the TV claim."** Medicare Advantage ≠ everything covered; Medicaid brings Extra Help; turning 65 opens the federal Medigap protection, "different from a refusal before 65"; "Keeping your current coverage in place while those details are checked is the safer next step." Question: doctors.
- Gaps (content, not behaviour): no reviewed statement about dual-eligible Special Needs Plans, so the TV plan was never named for what it probably is; no statement that advertised extras are plan-specific and can change each year. Both are candidates for pilot-rules r2. Latency on the first turn was the longest of the day.

## Walt · 70, Original + Plan G ($240) + PDP, wife says it's wasted, wants zero-premium Advantage, "can I go back next year?"
- Before the Medigap-return rule: the central distinction was there ("returning to Original Medicare and getting a Medigap supplement again follow separate rules… don't assume"), Open Enrollment and the Jan 1–Mar 31 MA period stated, but underwriting was hedged ("other protections may apply; the unresolved issue is…"). Turn 2 ("is $240 worth it for a healthy guy?"): what a supplement buys, "being healthy now doesn't make that protection worthless — but it doesn't establish that keeping it is the best value either"; no recommendation; asked prescriptions.
- **After the rule (replay):** "Outside protected Medigap enrollment periods or special rights, insurers can usually ask health questions and may refuse an application or charge more… Keeping your current coverage is a valid option while return rights remain uncertain… Parts A and B alone have no yearly medical spending cap. That protection matters even during years when you rarely see a doctor." Question: doctors.

## Scorecard, second set (9 turns + 2 replays)
- Third-party referral as the follow-up: 0.
- Blank/truncated: 0. One `ungrounded_literal` repair cycle in the day's log; the repair succeeded.
- Unsupported personal findings shown: 0 (Hank pushed twice for a plan pick; Gloria asked "can I get that?" and "should I drop Medicaid?"; Walt asked "is it worth it?").
- Wrong-footed by a trap: 0. Weakest spots were omissions, not errors: COBRA (fixed), underwriting bluntness (fixed), D-SNP vocabulary (open).

## Rules added this set
- `cobra_not_current_employment` → existing reviewed `cobra_timing`; confirm RC04.
- `medigap_return_underwriting` → `ma_trial_right` statement plus `medical_limit` evidence; no confirm target.
