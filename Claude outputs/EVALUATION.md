# Evaluation of the 15 profile runs on :8895 — November 13, 2026

For Chris. Covers the 12 runs logged in this folder (PP02, PP04–PP08, PP10–PP15) and the first three (PP01, PP03, PP09) in `../live-three-profiles-20261113.md`. Everything here came from the logs, from reading the code, and from offline probes in the repo. Nothing in this evaluation made a model call or touched a running server.

## The short version

1. **Most of what went wrong traces to a handful of causes, and all but three are confirmed in the code or reproduced offline.** They are small in code and large in effect. The build is not broken in many places; it is broken in a few places that every conversation passes through.
2. **Daylight is not recording what people say they already have.** Eleven of the 15 profiles already have Parts A and B. My own parser for "A and B since 2020"-style sentences recognized 2 of 15 when I replayed them offline. So there was no status line, and long-time enrollees were shown how to sign up for Parts A and B.
3. **One stuck question owned the conversation.** 56 of the 100 new turns ended on the same doctor-detail or medicine-detail question. In six runs the person had already given the practice or address being asked for.
4. **A shortcut swallowed people's messages.** While a doctor question is open, any message under 80 characters without a question mark is taken as the doctor's city. That is why four turns got no reply at all, and why "Female, and I've never used tobacco" was lost.
5. **The cards that teach the choice never appeared** because the trigger is a phrase list written around one test conversation. It matched 0 of 17 option-seeking messages from these profiles.
6. **Fifteen drafted Medicare statements have been waiting for your sign-off since November 9** (`pilot-rules-r2.json`). They include the $2,100 drug cap and the 20-or-more-employees rule. Until you accept them the chat cannot say them. This is not in the Brain's open questions; I have added it.

Two things I told you earlier were wrong, and one was overstated. They are corrected under "Corrections" below.

**My read on the pilot (C31):** I would not show this :8895 build to participants on November 17. The invitees come through the club network, so many will already be on Medicare, and that is the group this build serves worst. I am confident about :8895. I do not know how much of this :8894 shares, because it has not been run against these profiles; the doctor and medicine loops are :8895-only, but the lost replies, the fallback and the missing path card sit in shared files.

## What the runs measured

| Measure | Result | Target (UX playbook) |
|---|---|---|
| Status line right from the person's own words | 3 of 15 (PP01, PP11; PP03 one turn late). Wrong in 1 (PP12). Absent in 11 | Every run |
| Turns ending on a question already shown earlier | About 6 in 10 of the 100 new turns | 0 repeats |
| Turns ending on the doctor-detail or medicine-detail question | 56 of 100 | — |
| Turns where the person got no answer | 11 of 100: 5 with no reply, 4 double fallbacks, 2 server failures | 0 |
| Two-path card shown | 0 of 15 | Whenever the person asks about options |
| "What each path trades" card shown | 0 of 15 | When a cost preference is stated |
| A button into the plans offered from the conversation | 0 of 12 (PP04's prices were ready from turn 2) | Always |
| Doctors matched to the directory | 0 in 15 runs, including six mentions of real Collier doctors | — |
| Runs ending in one of the six finishes | 0 of the 12 new runs | Every run |
| Final teach-back handled | 9 correct, 1 correct but missing the penalty, 2 fallbacks | — |
| Invented plan names, prices or dates | None seen in 100 turns | 0 |
| Reply time | Median 17.6 s; a third of turns took 20 s or more; two failures at 93 s | — |
| Cost | $6.09 for 12 runs; $0.52 a conversation. 16 turns needed a third model call. $0.53 (9%) went to turns that answered nothing | — |

One caution on the repeat numbers: the script types each profile's messages in order, whatever was asked, and taps no buttons. A real person would answer some of these questions. I have separated true repeats (asked after the answer was given) from pending ones in the findings.

## How sure each cause is

- **Reproduced offline:** I ran the code on the profiles' own sentences and got the same failure.
- **Read in code:** the line that does it is identified; not executed.
- **Likely:** consistent with the evidence, but confirming it needs the server's log from the run, which is in the Terminal window on your Mac. I did not open it, since that is a computer-access session.

## Findings and fixes

### A. Daylight does not record what people already have

**What happened.** "A and B started June 1, 2019", "I've had Parts A and B since February 2025", "Original Medicare since 2020, Plan G, and the AARP Rx Saver drug plan": none of these set the Parts A and B status. Plans step 1 then showed "Not confirmed yet" and "How to sign up for Part A and Part B" to PP04, PP05, PP06, PP10 and PP13. PP12, an HMO member since 2024, got "Part A: not confirmed · Part B: not confirmed. Next: choose a Medicare Advantage plan." Existing policies (Plan G, Plan F, a drug plan) were never shown on steps 2 and 3.

**Why.**
- *Reproduced offline.* `enrollment_flow.reports_from_text` recognized 2 of 15 statements (PP01, PP11). It needs the word "Part" or "Medicare" directly before "started", and has no rule for "since".
- *Read in code.* Nothing derives Parts A and B from the coverage a person names. Someone in a Medicare Advantage plan has both parts by definition.
- *Reproduced offline.* Two misreads are mine: "No supplement or drug plan yet" records Medigap as "not needed" (PP11, who came to buy one), and "pick one up later" inside a question records prescriptions as "Decide later" (PP08). "I'm keeping the Plan G" (PP07) records nothing.
- *Likely.* The model's own proposals for these facts were dropped or held for confirmation by the capture rules (for example, a start date in the past can be scoped as "not current"). The log would show which rule.

**Fix.** Replace the sentence patterns with a small coverage reader that works in three steps:
1. Find each coverage mention: Parts A/B or "Original Medicare"; Medicare Advantage, HMO or PPO; Medigap, "supplement" or a plan letter; a drug plan.
2. Attach its time words ("since", "started", "starts", a year alone) and its polarity ("no", "never", "not yet").
3. Apply rules:
   - A part with a past or "since" date is active from that date; a future date means it starts then.
   - A current Medicare Advantage plan or Medigap policy means Parts A and B are active, labeled as derived.
   - A policy the person has is shown as "You have Plan G", which is a fact. It becomes "keep" only when they say so.
   - "Not yet" leaves a step undecided. Nothing is recorded from a question or an "if".

**Method.**
1. Build the test list first: every coverage sentence in the 15 transcripts with the facts it should produce, plus the three misreads as negatives. It runs offline, at no cost, in `test_enrollment_flow`.
2. Write the reader in `enrollment_flow.py`; keep `reports_from_text` as its caller so nothing else changes.
3. Add the derived basis to the status line: "(from your Medicare Advantage plan)". The source is the statement `ma_requires_a_and_b`, which is in the unsigned r2 set (see F).
4. Step 1 of the dashboard: when both parts are active, show the dates and collapse the sign-up guide. Steps 2 and 3: show "You have …" with "Keep it" and "Compare" as the two choices.
5. Pass: 15 of 15 offline, then a live re-run (see the gates at the end).

**Owner.** Claude. **From you:** sign-off on the derived label and "You have Plan G"-style lines.

### B. A shortcut swallows messages while a doctor question is open

**What happened.** Four turns made no model call and showed no reply: PP05 t7, PP11 t2, PP11 t7, PP14 t7. PP11's sex and tobacco answer was lost, so the one profile whose whole question was "what would a supplement cost me" never reached a price. PP14's actual decision ("I'd give up the Part B money back for him") got silence.

**Why.** *Read in code.* `conversation_checks.text_answer` treats any message under 80 characters, with no question mark and none of nine listed words, as the answer to "What city or practice is Dr. … in?". The sentence then goes to the directory as a town or practice. The directory finds nothing, or rejects it as too long, and in three of the four cases the page then showed "this doctor check is unavailable".

**Fix.** The local shortcut accepts only a tapped choice, or typed text that exactly matches a listed choice, a date, a number, a ZIP code or a known town. Any other sentence goes through the normal turn, with the doctor question still open, so the model can read a practice or town out of it and everything else in the message is recorded.

**Method.** A journey test from PP11's words: open doctor question, then "Female, and I've never used tobacco." Expect sex and tobacco recorded, a reply, and the doctor question still open. One changed condition in `text_answer`; no other file.

**Owner.** Claude.

### C. One question owns the conversation

**What happened.**
- 56 of 100 turns ended on the doctor-detail or medicine-detail question. PP02 saw the doctor question seven turns running; PP12 saw the medicine question on all nine.
- True repeats: in six runs (PP02, PP04, PP05, PP10, PP13, PP14) the person had already given the practice or the address. PP13 was asked "Are there doctors or hospitals you want to keep?" after naming both. PP04 was asked which parts she has after saying so.
- The re-ask wording degrades: "Exact pharmacy and retail or mail order should we use?", "Including your therapist?", then "When you're ready: …" in identical words for the rest of the conversation.
- The medicine question asks four things at once: quantity, days' supply, exact pharmacy, and retail or mail order.

**Why.**
- *Read in code.* A check question has no give-up rule. It stays the next question until answered or tapped away.
- *Reproduced offline.* `ux_pass.shorter_question` makes the second wording by keeping the text after the last comma. That is where the fragments come from.
- *Read in code.* The third wording, "When you're ready: …", is then reused unchanged every turn after.
- *Read in code.* In PP13, a held confirmation about the doctor blocked the directory check from ever starting, so the address was asked four times and nothing was searched.

**Fix.**
1. **A question budget.** Ask once. If the person talks about something else, ask once more in a short fixed wording. If they pass it again, park it: one line says so, a small "1 detail parked" chip holds it, and the conversation moves to the next useful thing. A parked question comes back only when the person taps it, or when it is the last thing standing between them and what they asked for.
2. **Fixed short wordings only.** Add doctors, medicines, travel and insurance to the short-wording table; delete the last-clause shortcut and both prefixes ("Just to confirm:", "When you're ready:").
3. **One medicine detail at a time, with defaults.** Take what the person said ("two a day" is 60 for 30 days), assume a 30-day supply picked up at the pharmacy they named, show that as one editable line, and ask only for what is really missing, with buttons.
4. **A held confirmation never blocks the directory search.**

**Method.** The budget lives in the visit record that already tracks what was asked (`VisitLedger`): add "passed" counts per question. Tests from PP02 (doctor), PP12 (medicine) and PP08 (travel): no question appears more than twice, and none appears after its answer. The medicine defaults need the estimate service to accept them; that is a Codex handoff.

**Owner.** Claude; Codex for defaults in the drug estimate. **From you:** yes or no on assuming 30 days and retail pickup; sign-off on the parking line.

### D. Doctors are not found, and "not found" is shown as "unavailable"

**What happened.** No doctor was matched in any of the 15 runs. Six mentions were of real Collier doctors that the profile set took from the directory files (Wise, Speake twice, Craig, Albagdadi, Josephson). PP14 gave a full street address and suite and was still asked what city or practice. Fictional doctors, which are the set's negative controls, produced "this doctor check is unavailable… I can't establish this result from the available evidence", shown for five turns in PP06.

**Why.**
- *Read in code.* The whole entry is searched as a name: "Dr. Mark Speake at NCH on 9th Street", "Dr. Kelly Craig, my internist for years". Only "X in Place" is split. Every word must match the doctor's name, so "NCH", "9th" and "Street" make the search fail.
- *Read in code.* The directory raises an error when no word of the name is known or when the text is over ten words. The conversation maps every such error to the "unavailable" panel.

**Fix.**
1. Split an entry before searching: name, practice ("at …"), town ("in …"), street ("on …"); drop role words ("my internist for years", "for primary care").
2. Search by name first, then narrow by town or practice. A surname alone ("Dr. Albagdadi") returns the candidates with their towns, which is what PP13 needed.
3. Unknown names and over-long text go to the existing not-found line ("I couldn't find … so plan networks aren't checked for this doctor"), said once. "Unavailable" is only for a real data fault.

**Method.** A table test of the eleven doctor entries from the logs and their expected split. A scripted directory test for the three error codes. Then one on-screen check against the real directory for Wise, Speake, Craig, Albagdadi and Josephson, which needs no model call.

**Owner.** Claude for the split and the mapping; Codex if the directory should return an empty list instead of raising.

### E. Turns that answer nothing

**What happened.** Besides the four swallowed turns in B:
- **Double fallback, 4 turns** (PP02 t1, PP08 t2, PP10 t9, PP11 t8): "I don't have a checked answer to that question here yet, so I won't guess." followed by "I couldn't finish that answer. Here is the part I'm sure of." with nothing after it. Two were final teach-backs.
- **Billed and blank, 1 turn** (PP10 t4): three calls, no reply, and the answer arrived a turn late in place of a reply to his next message.
- **Server failure, 2 turns** (PP07 t2, PP14 t5): 93 seconds, then "The service could not complete this request." Both were billed, and both medicine lists were lost.

**Why.**
- *Read in code.* The fix that removed "I couldn't finish" (CV-03) covers only one of the two failure paths. When the checker drops the model's prose but keeps its question, `natural_flow.py` line 1701 adds the notice back and nothing removes it.
- *Likely.* The checker rejected those replies because they restated the person's coverage ("your HMO", "your Plan G") while no coverage was on record, which is finding A again. The first three runs logged that exact code twice (`missing_coverage_reference`).
- *Read in code.* A clean-up step blanks a reply that only repeats earlier sentences and lets the question "carry the turn". It does not check whether the person had asked something.
- *Likely.* The 93 seconds is one normal call plus two 40-second timeouts, ending in an error type the turn handler does not catch. Both failures were on a message containing "Metformin ER 500, two a day". The traceback is in the Terminal log.

**Fix.**
1. Remove the notice on the second path too, so a fallback is always one sentence and the next question.
2. One rule at the end of every turn: a typed message always gets a sentence back. If nothing else survives, code builds it from what was just recorded ("Got it: …").
3. Never blank a reply on a turn where the person asked something.
4. Catch any unexpected error in a message turn and return the calm fallback instead of a 500. Keep the person's message in the conversation and in the box, with "Send again".
5. Cap a turn at about 45 seconds in total, and show "Still working on that…" after 12.
6. Make the fallback more useful: when a question fails the check, answer with the accepted statements that match its terms, which the code already does on the other path.

**Method.** Extend `test_forced_failure` to the kept-question path. Add an invariant test over all 15 replayed transcripts: no message turn returns an empty reply. Add a test that raises an arbitrary error mid-turn and expects a normal response. The 93-second cause needs one look at the Terminal log first.

**Owner.** Claude. **From you:** a computer-access yes to read the Terminal log; sign-off on "Still working on that…" and "Send again".

### F. The chat cannot say rules that were never accepted

**What happened.** PP07 asked about a yearly limit on drug costs and was told there was no supported rule. PP09 was never given the 20-or-more-employees rule. PP03's "about two months" was sent to "confirm with Medicare". PP12's insulin question, PP04's G versus N and PP05's Plan F question were refused. PP08 was told not to drop his drug plan, without the penalty.

**Why.**
- *Read in code.* `pilot-rules-r2.json` is marked `pending_owner_review`, so the loader skips it. It holds 15 statements drafted on November 9, with sources. Among them: the 2026 Part D cap ($2,100), the small-employer rule, the 8-month Part B special enrollment period, the 2-month drug-plan period after losing creditable coverage, the Medigap open enrollment rule, and "Medicare Advantage requires Parts A and B". One of the 15, `about_daylight`, still has blanks for you to fill.
- *Read in code.* There is no statement at all for the insulin cap, or for who can still buy or keep Plans C and F.
- *Read in code.* The twelve plan-letter lines you signed off live only in the browser file for the Medigap page. The model is never given them, so the chat cannot compare G and N.
- *Read in code.* The accepted Part D penalty statement is offered only to someone on Original Medicare with no drug plan, not to someone talking about dropping one.

**Fix.**
1. You review the 15 r2 statements against their source pages and accept, edit or strike each. I can lay them out as a one-page sign-off list with the source link beside each.
2. I draft three new statements with sources for your sign-off: the insulin cap; Plans C and F for people eligible before 2020 and for current holders; and the Part D penalty when dropping coverage.
3. Feed the signed plan-letter lines to the model as accepted statements, so "G or N" gets the two lines side by side.

**Method.** No code is needed for item 1 beyond changing the review state once you sign. The check is in the live re-run: PP03, PP07 and PP09 should each get the rule they were refused.

**Owner.** You for the sign-off; Claude for drafting and wiring.

### G. The cards that teach the choice never appear

**What happened.** No two-path card and no "What each path trades" card in 15 conversations. PP13 opened with "Which way of doing Medicare lets me keep both?" and PP14 with "What are my options?". PP04, PP06 and PP13 each stated a cost preference.

**Why.** *Reproduced offline.* Both cards are tied to `find_intent`, a list of phrases such as "what's the best plan" and "show me the plans". I ran it on 17 option-seeking messages from the profiles. It matched none.

**Fix.** Trigger the cards from the state of the conversation, not from phrases:
- **Two-path card:** the first turn where the ZIP is known, no path is chosen, the card has not been shown, and the person either asks about cost, options, switching or keeping a doctor, or names both paths, or states a priority.
- **Trade-off card:** the turn a cost preference is recorded.
- **People who already have coverage and are reviewing one piece** (PP07, PP08, PP15): not the two-path card. Show "What you have now" from finding A, with the piece under review open.
- Later, add a small "what are they asking for" field to the model's reading step, checked in code against a quote from the message. The reading step already returns a goal quote, so this is an extension, not a new call.

**Method.** The 17 messages become the test list, each with the card it should produce. Add the review cases as negatives for the two-path card.

**Owner.** Claude. **From you:** sign-off on the "What you have now" card wording.

### H. The conversation never hands the person their plans

**What happened.**
- PP04's Medigap prices were ready from turn 2. No button appeared in eight turns.
- PP12's line said nothing was left from turn 6. Nothing was offered.
- PP15 asked for the cheapest drug plan. The drug plan list was ready from turn 1, yet the line read "3 details left to see plans and prices" for all eight turns.
- Replies point to the plans in words: "The Original Medicare (step 3, prescriptions) tab on the Plans page now lists…".

**Why.**
- *Read in code.* This morning's fix shows "See your Medigap prices" only when no question is open. A question is nearly always open, so the button never shows. That one is mine.
- *Read in code.* The what's-left line counts Medigap pricing details whatever the person is here for. PP15's three details were Medigap pricing details, for a Medigap price nobody asked about.
- *Read in code.* The model is told the tab's name, including my "(step 3, prescriptions)" text, and repeats it.

**Fix.**
1. When a list becomes ready, show it once, in the conversation, as a short code-built line with a button ("Your Medigap prices are ready" · See prices). It stays in the transcript above later messages. It is not tied to whether a question is open.
2. The what's-left line follows what the person asked for: drug plans for PP15, Medigap for PP04, both paths when undecided.
3. Tell the model that a button exists, not what the tab is called. Strip any "(step …) tab" wording from replies in code.

**Method.** View tests for the ready line at the three widths; a journey test for PP15 (line empty from turn 1, button present) and PP04 (button on turn 2 with the insurance question still open).

**Owner.** Claude. **From you:** sign-off on the ready lines.

### I. Text is cut and assembled wrongly

**What happened.** "We'll keep Dr. Speake and Dr. For your preference for predictable bills…" (PP13). "Yes, that's right" offered beside six insurance choices (PP02, PP10) and beside an open address question (PP13). "Do you use tobacco of any kind?" put to a daughter asking for her father (PP05). A question about turning 65, with no buttons, put to someone already on Medicare (PP11). The insurance choices have no option for a marketplace plan (PP01, PP11, PP13).

**Why.**
- *Reproduced offline.* The sentence splitter breaks at every period: after "Dr.", inside "$236.50", inside "U.S.". Every clean-up rule that drops "a sentence" drops a fragment. In PP13 the dropped piece was "Albagdadi at the center of the comparison." because it had been said the turn before. The same splitter could cut an amount in half.
- *Read in code.* When a held confirmation is open, the page draws the original question's full list of choices and adds "Yes, that's right".

**Fix.**
1. A splitter that does not break after titles and abbreviations, inside numbers, or before a lowercase word. A rule that a clean-up may only drop whole sentences, and leaves the reply untouched if what remains does not read as complete sentences.
2. A confirmation shows only "Yes, that's right" and "No, let me fix it". An open question shows no confirm button.
3. Helper wording: every question for a helper uses the person's name or relationship.
4. Add "A plan I buy myself (marketplace)" to the insurance choices.
5. Do not ask when someone turns 65 once they have said they are on Medicare.

**Method.** Splitter tests: the PP13 reply, an amount with cents, "St.", "U.S.", a phone number. A view test for the confirmation panel. Item 4 adds a choice that changes what gets recorded, so it needs Codex's enrollment record to accept it.

**Owner.** Claude; Codex for the new insurance value.

### J. The identifier guard misses near-misses

**What happened.** PP06 typed "My Medicare number is …" with a number. It went to the model. The reply asked her not to share it.

**Why.** *Reproduced offline.* The guard is working as written. It blocks valid Medicare numbers in every spacing I tried, and Social Security numbers. The profile's fictional number starts with 0, which no real Medicare number does, so the exact-shape rule let it pass. The same is true of a real number with one typo.

**Fix.** Add two looser rules for text a person types:
1. After the words "Medicare number", "MBI", "Social Security number", "SSN" or "my social", block any following 9-to-13-character code that contains four or more digits.
2. Block any 11-character code written 4-3-4 with at least three letters and four digits, whatever its first character.

Plan IDs such as H1036-286 have one letter and a different grouping, so they are not caught.

**Method.** Guard tests: the profile's opening message, three typo variants, and a list of things that must still pass (plan IDs, phone numbers, ZIP+4, dates, dollar amounts). This should land before any pilot session, because consented transcripts are saved.

**Owner.** Claude.

### K. The chat spoke a recommendation

**What happened.** PP10 asked "Would you actually recommend keeping the coverage I already have?" and got "Yes—as a practical next step, I'd keep your current coverage in place while comparing alternatives". PP06 demanded yes or no on her trial right, got "Yes", and the next turn got "My earlier 'yes' was too broad."

**Why.** *Read in code.* The checker blocks "you should switch" and similar second-person directions. It has no rule for a first-person recommendation. Rights that depend on dates are left to the model's prose.

**Fix.**
1. Add first-person recommendation wording to the checker ("I'd keep", "I would switch", "I recommend", "my recommendation").
2. A "should I" or "would you recommend" question gets a fixed line and the code-built comparison: what the person said matters, and how each path fits it. Proposed line: "I can't make that choice for you here. This is how each path fits what you told me."
3. A trial-right card built in code from the accepted statement and the person's own dates: first Medicare Advantage plan, joined at 65, start date, and the month the 12 months end.

**Method.** Checker tests with PP10's reply as the failing case and "Not necessarily" answers as passing ones. The card follows the timing card's pattern: dates computed in code, each labeled "(you told me)".

**Owner.** Claude. **From you:** where a protective caution ends and a recommendation begins ("he shouldn't drop Plan F on that assumption" is a caution; "I'd keep your coverage" is not). I would also put that question to counsel with the Option A answer.

### L. Smaller items

| Item | Cause | Fix |
|---|---|---|
| "he" for Priya Talden (PP02) | Model wording before the first name was given | Replies use the doctor's name, not a pronoun, until a title or name settles it; add to the model's instructions |
| "Suggested path: Original Medicare" for PP02 | The evaluation-only sort weighs "keep your doctors" alone; current coverage does not hold it | Your call: should being in a plan now hold the suggestion, as current job coverage already does? |
| "Your medicines" notice stacked above an unrelated question (PP07) | The not-checked note is drawn inside the question panel | Move it to the transcript, once |
| PP08's ZIP answer got a generic Medicare sentence | Fallback with nothing related to say | Covered by E |
| "Outside the 6-month Medigap Open Enrollment Period" for someone whose Part B has not started (PP03) | Existing rule | Open as playbook issue 52 |

## What worked

- No invented plan name, price or date in 100 turns. The checker's cost is false rejections, not false statements.
- Nine of twelve final teach-backs were corrected clearly and accurately (PP02, PP04, PP05, PP06, PP07, PP12, PP13, PP14, PP15).
- The helper case (PP15) was handled well throughout, and the Ozempic card came at the right moment.
- First answers were often strong: PP13 and PP14's openings set out both paths accurately in plain words.
- PP11's status line and PP03's call branch worked as designed.
- The Medicare number was not echoed, and the reply told her not to share it.

## Corrections to what I told you earlier

1. **"Approved facts refused."** The $2,100 cap, the 20-employee rule and the two-month rule are drafted but not accepted. The insulin cap, the Plan F rule and G versus N in the chat are not written at all. Only the Part D penalty is accepted and was left out.
2. **"The identifier guard did not block it."** The guard blocks real Medicare numbers. The test number is deliberately invalid. The gap is real but narrower than I said: typos and near-misses.
3. **"Total yearly costYour priority" runs together.** That was my text capture. On screen the tag has spacing. Not a bug.
4. **PP05 "He's male" not recorded.** It was recorded on that turn. The tobacco category was then asked for confirmation, which is reasonable after "a cigar most weekends".

The README in this folder is corrected to match.

## Proposed order for the next push

| Wave | What | Why first |
|---|---|---|
| 0 | You: sign r2; answer the decisions below. Me: read the Terminal log (with your yes) | No build; unblocks F and E |
| 1 | Stop losing what people say: B (swallowed messages), A (coverage reader), E (always answer; catch failures), J (guard) | Everything downstream depends on the record being right |
| 2 | One question never owns the conversation: C (budget, wordings, medicine defaults), D (doctor split, not-found), I (splitter, confirmation panel) | Removes most of the repeats |
| 3 | Show the choice and the plans: G (cards from state), H (ready line, what's-left), "What you have now" | The product's actual promise |
| 4 | F drafting and wiring, K (recommendation rule, trial-right card) | Needs your sign-offs |

Each wave starts with its offline tests, built from these transcripts, and is checked on screen at three widths before any live spend.

**Then a cleared live re-run:** PP12, PP04 and PP11 first (about $1.60), then all 15 (about $8). Gates:

| Gate | Pass |
|---|---|
| Status line right by the turn the person states their coverage | 13 of 15 or better |
| Message turns with no answer sentence | 0 |
| Double fallbacks | 0 |
| A question shown after its answer was given | 0 |
| Any question shown more than twice | 0 |
| Two-path card or "What you have now" shown | Every run |
| A button into the plans offered when a list is ready | Every run |
| Real doctors from the profile set matched | All six mentions |
| "Unavailable" shown for a doctor who is simply not listed | 0 |
| First-person recommendations | 0 |

## Handoffs to Codex

1. A per-turn trace on :8895, codes only and no message text: stage times, calls, cost, each proposed fact with its decision and reason, the checker's rejection code, the question and cards shown, and the location of any unexpected error. This also answers C34 (cost per conversation). Three causes above are "likely" only because this does not exist.
2. The directory returns an empty result for an unknown name instead of raising, or documents which codes mean "not found".
3. The drug estimate accepts defaults (30-day supply, retail pickup, quantity from the stated dose).
4. The enrollment record accepts a derived basis for Parts A and B, an existing policy as a fact separate from "keep", and a marketplace value for current insurance.

I can write the Codex prompt once you have reviewed this.

## Decisions and sign-offs I need from you

1. Review and accept the 15 r2 statements. I will prepare the sign-off sheet.
2. May I read the Terminal log from the runs (one computer-access session, no model call)?
3. Medicine defaults: assume a 30-day supply and pickup at the named pharmacy, shown and editable?
4. Parking a question after it is passed twice: agreed?
5. New wording, all without Medicare facts except the first:
   - "(from your Medicare Advantage plan)" and "(from your Medigap policy)" as the basis for Parts A and B
   - "You have Plan G." with "Keep it" and "Compare"
   - "I'll leave Dr. Talden's office open for now. You can add it any time."
   - "Your Medigap prices are ready." and "Your drug plans are ready."
   - "Still working on that…" and "That took too long, so I stopped. Your message is still here. Send again?"
   - "I can't make that choice for you here. This is how each path fits what you told me."
6. Should being in a plan today hold the "suggested path", as job coverage does?
7. Pilot timing (C31): given the above, do you want three profiles run on :8894 (about $1.60) to see what participants would see on November 17?

## What I could not determine

- Which capture rule dropped each fact the model proposed (A), which checker rule rejected each fallback reply (E), and what raised the two 93-second failures (E). All three are in the Terminal log.
- Whether the empty question panel captured in PP10 and PP11 draws an empty box on screen. It needs a look.
- How :8894 behaves on these profiles.
- Tablet and phone widths. Every run was at 1280 pixels.
