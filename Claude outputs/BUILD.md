# What was built from the evaluation — November 13, 2026 (evening)

Chris: "Systematically address every single point you mentioned in evals and implement the fix. I approve all suggestions. Just go on all yourself, no hand off."

Status in one line: **built and passing offline; not restarted, not seen on screen, not run live.** Nothing a person sees on :8895 or :8894 has changed yet. The changes load when the servers restart.

## One correction to the evaluation first

**Finding F was wrong about the cause.** I wrote that the chat could not state the $2,100 drug cap, the 20-employee rule or the two-month rule because `pilot-rules-r2.json` was never signed. That file is unsigned, but on :8895 it is not what matters. The reviewed catalog you approved on November 12 (71 facts, D159 and D163) already holds all three, plus the Part D penalty and the Medigap switching rule. They were not reaching the model because the catalog is searched by exact phrases: "drug cap" matches, "any limit on what I could end up paying for drugs in a year" does not. So I did **not** accept r2, and it does not need your review for this. The fix is in how facts are found (see F below). The Brain's C36 is corrected.

## What changed, by finding

| Finding | Built | Where | Offline proof |
|---|---|---|---|
| **A. What people already have** | A coverage reader for "A and B since 2020"-style sentences. It reads 14 of the 15 profile statements; the 15th ("No A, no B") now answers the parts question as "neither" | `enrollment_flow.py` | 15 sentences and 11 that must record nothing |
| | Parts A and B derived from a Medicare Advantage plan or a Medigap policy, labeled "(from your Medicare Advantage plan)" | `enrollment_flow.py` | PP12's journey: no more "not confirmed" |
| | What a person has is a fact: "You have Plan G." with Keep it, Compare, Decide later. It is not recorded as a decision | `enrollment_flow.py`, `plans-workspace.js` | PP15's journey |
| | A "What you have now" card, once | `enrollment_flow.py`, `enrollment-view.js` | PP15's journey; view test |
| | Three misreads fixed: "No supplement… yet", "pick one up later" inside a say-back, "I'm keeping the Plan G" | `enrollment_flow.py` | PP11, PP08, PP07 sentences |
| **B. Swallowed messages** | A typed sentence is taken as the doctor's town only if it is a town, a ZIP code or a practice name on its own | `conversation_checks.py` | The four swallowed messages, and nine that must still work |
| **C. One question owning the conversation** | Shown once, shown once more, then parked. Doctor and medicine checks park with one line; other questions stop being candidates. The ZIP code and "who is this for" are never parked | `conversation_checks.py`, `natural_flow.py`, `ux_flow.py`, `ux_pass.py` | A question passed twice is replaced by the next one |
| | A second ask uses a fixed short wording. The last-clause shortcut and both prefixes are gone | `ux_pass.py`, `ux_flow.py` | "Including your therapist?" can no longer be produced |
| | A held confirmation about something else no longer blocks the doctor search | `conversation_checks.py` | Read in code; needs the live directory |
| **D. Doctors** | Only the name is searched; "at NCH", "in Naples" and "my internist for years" are split off | `conversation_checks.py` | Eleven entries from the logs |
| | An unknown name is "not found", said once. "Unavailable" is only a real data fault | `conversation_checks.py` | Code list; needs the live directory |
| | Someone who already gave the practice or town is not asked for it again | `conversation_checks.py` | Read in code; needs the live directory |
| **E. Turns that answer nothing** | "I couldn't finish that answer" removed on the second failure path too, and the fallback uses a matching checked statement when there is one | `ux_flow.py` | Existing forced-failure tests still pass |
| | A reply is never blanked on a turn where the person asked something; a typed message never meets silence | `ux_flow.py`, `natural_flow.py` | PP10's case by rule; continuity tests pass |
| | An unexpected error returns one calm line, keeps the message in the box, and the person can send again | `natural_flow.py`, `advisor.js` | A forced error mid-turn |
| | A request that already took 20 seconds is not sent a second time | `natural_agent.py` | Connection-recovery tests pass |
| **F. Rules the chat can state** | Approved catalog facts are found by the person's own phrasing (word groups, no new wording) | `pilot_knowledge.py`, `pilot-knowledge-concepts.json` | Five questions from the logs find the right fact |
| | Three checked statements with their Medicare.gov sources: the insulin limit, Plans C and F, Plan G beside Plan N | `enrollment-content.json`, `enrollment_flow.py` | Each is found by the question that was refused |
| **G. Cards** | The two-path card, the trade-off card and "What you have now" are triggered by the state of the conversation. The phrase list is widened too | `ux_flow.py`, `ux_pass.py` | 13 of 13 option-seeking messages; state rules read in code |
| **H. Plans handoff** | "Your Medigap prices are ready." with a button, once, in the conversation, whatever question is open | `ux_flow.py`, `enrollment-view.js` | View test |
| | The what's-left line follows what the person is here for | `ux_flow.py` | Read in code |
| | Replies say "the Plans page", never a tab or a step | `enrollment_flow.py` | Six sentences from the logs |
| **I. Text** | A sentence splitter that knows "Dr.", "$236.50" and "U.S." | `ux_pass.py` | PP13's cut sentence |
| | A confirmation shows "Yes, that's right" and "No, let me fix it" only | `advisor.js` | Syntax check only; needs a look |
| | A helper is not asked about "you" in the stock wordings | `ux_pass.py`, `ux_flow.py` | One case |
| **J. Identifier guard** | Near-misses are blocked: a code after "Medicare number" or "Social Security number", and any 4-3-4 code of letters and digits | `identifier_guard.py` | Six blocked, nine allowed, old tests pass |
| **K. No spoken recommendation** | The checker rejects "I'd keep…", "I recommend…"; a request for a pick gets the fixed line and the two-path card | `natural_agent.py`, `ux_flow.py` | PP10's reply rejected; six cautions allowed |
| **L. Smaller** | Being in a plan today holds the "suggested path" | `recommendation_engine.py` | One case |
| **Trace** | One line per turn on :8895: times, calls, which report was accepted or not and why, the checker's code, the question and cards shown. No words | `natural_flow.py`, `demo_server.py` | A test that looks for a typed name in the file and finds none |

## Not built

1. **Medicine defaults** (assume a 30-day supply at the named pharmacy). The medicine question is now asked twice at most and then parked, but the four-part question itself is unchanged. Defaults need the drug estimate service to accept them, and I could not run that service here.
2. **The trial-right card.** It needs the date a person joined their first Medicare Advantage plan, which nothing records yet.
3. **A marketplace choice** in the insurance question. It needs a new value in the shared question list.
4. **The "Your medicines" notice** still sits inside the question panel.
5. **Reply speed.** Not addressed, beyond not retrying a slow request.

## Wording now in the build

Approved by you on November 13, as listed in the evaluation: both "(from your …)" labels; "You have Plan G." with "Keep it" and "Compare"; "I'll leave Dr. …'s office open for now. You can add it any time."; "Your Medigap prices are ready." and "Your drug plans are ready."; "That took too long, so I stopped. Your message is still here. Send again?"; "I can't make that choice for you here. This is how each path fits what you told me."

Written by me in the same pattern, for you to strike or change:
- "You have a Medigap policy." / "You have a drug plan." / "You have a Medicare Advantage plan." / "What you have now" (card title)
- "Your Medicare Advantage plans are ready."
- "I'll leave your medicine details open for now. You can add them any time."
- "Something went wrong on our side, so I stopped. Your message is still here. Send again?"
- "No, let me fix it" / "Type the right answer in the message box."
- "Decide later" beside Keep it and Compare
- Second-ask wordings: "What coverage do you have today?", "Any doctors or hospitals to keep?", "Which medicines should I include?", "Any routine care away from home?", "Which office do you visit for this doctor?", "What are the refill details for these medicines?"
- "You have a Medicare Advantage plan now. Keeping it and changing it are both open, so Daylight does not suggest a path yet."

Three Medicare statements, each checked against its source today:
- **Insulin** (Medicare.gov, Insulin): "A Medicare drug plan charges no more than $35 for a one-month supply of each insulin it covers, and the deductible doesn't apply to insulin. The $35 limit is for covered insulin; other medicines follow the plan's own costs."
- **Plans C and F** (Medicare.gov, Medicare Supplement Insurance overview): "Plans C and F aren't sold to people who became new to Medicare on or after January 1, 2020. Someone who already has Plan C or Plan F can keep it."
- **Plan G and Plan N**: the two plan-letter lines you signed on November 12, joined.

## What is shared with :8893 and :8894

Nothing on :8894 changes until :8893 restarts, and I have not restarted it. When it does, these fixes load there too, because they are in shared files:
- the sentence splitter, and second asks in fixed wordings;
- no "I couldn't finish that answer" notice; no blank reply when the person asked something;
- the calm error line instead of a 500; no second try of a slow request;
- the identifier guard's near-miss rules;
- the checker's rule against first-person recommendations.

Everything else is on the two-path build only: the coverage reader, parking, doctor split, cards, ready buttons, catalog matching, the three statements and the trace.

## Tests

- New: `tests/test_eval_20261113.py`, 28 tests, each from a profile's own words. One new view test.
- The enrollment, PP16 journey, panels, identifier, knowledge and rules suites: 147 tests, all passing.
- I ran about 100 of the 121 test files. Every failure I saw was either in `known-failures.json` or fails the same way on this morning's code (checked by running the same test against the saved copies). Three older tests were updated because the behavior they described changed on purpose: the tab wording, "You have a Medigap policy.", and the calm error line.
- Not run here: the unified demo tests and the doctor-check tests, which need database libraries this sandbox does not have. That is why the doctor fixes say "needs the live directory".
- `changes-evalfix.patch` in this folder is the full difference from this morning's files. Nothing is committed.

## Next, each needing your yes

1. Read the Terminal log from the afternoon runs before it is lost, then restart :8895 (one computer-access session).
2. Look at the build on screen at three widths, including one doctor search against the real directory. No model call.
3. A cleared live re-run: PP12, PP04 and PP11 first (about $1.60), then all 15 (about $8), against the gates in the evaluation.
