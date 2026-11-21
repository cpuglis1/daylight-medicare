# Hand tests for the advisor chat (D155) · November 21, 2026

Start: `python3 alternatives/advisor-first/server.py`, then `python3 alternatives/advisor-first/ui-8894/serve.py`; open http://127.0.0.1:8894 and click **Turns** to open the side panel (Facts saved, Tool calls, Model calls, Checks fired, Next question). Start a fresh visit (new private window) for each script.
Cost: live turns spend Daylight's API budget, about $0.05 to $0.10 per turn (unverified estimate); the full set is roughly 50 to 60 turns.
All people, ZIPs, doctors and numbers here are fictional. Never type a real or fake SSN, Medicare number or bank number.
Probe ids match `alternatives/advisor-first/config/conversation-checks.json` (simulated twins: `tools/evaluation/conversations/cases/`); field names come from `turn_trace.py`, others are marked "(field name may differ)".

## 1. Son signs up his father (right_person, one_question)
Type: `My dad turns 65 in February and I'm handling his Medicare sign-up. Where do we even start?` then `He's in 34106.`
What to check:
- Reply says "your dad" or "he", never "you" for the father's facts.
- Facts saved shows `subject.role: → someone`.
- Facts saved shows `comparison.scope.zip: → 34106` on turn 2.
- Each reply ends with exactly one question; Next question is not the ZIP again.

## 2. Self, then "actually it's for my mom" (reconfirms_on_switch, right_person)
Type: `Hi, I have some Medicare questions about drug coverage.`, `Me, I guess.`, `34102.`, then `Wait, actually this is for my mom, not me. I'm 62. She's the one on Medicare.`
What to check:
- Turn 2 Facts saved shows `subject.role: → self`; turn 4 shows `subject.role: self → someone`.
- Turn 4 reply asks to confirm Mom's ZIP instead of reusing 34102; wording switches to "your mom" or "she".
- Facts saved on turn 4 clears or flags the old ZIP (field name may differ); it is not silently kept.
- Then type `Mom is in 34104.` and check Facts saved shows the new ZIP.

## 3. Husband, then "it's me" (reconfirms_on_switch, right_person)
Type: `I'm asking for my husband Gil. He's 67 and has Medicare. Does he need to do anything this fall?`, `We're in 34107.`, then `Actually, scratch that, Gil is fine. It's me who needs help. I turn 65 in March.`
What to check:
- Turn 1 Facts saved shows `subject.role: → someone`; turn 3 shows `someone → self`.
- After turn 3, wording is "you", and Gil's Original Medicare is not applied to her (`coverage.current` is empty or re-asked).
- Daylight checks that 34107 still applies to her rather than assuming it.

## 4. "I don't know" three times (no_reask, one_question)
Type: `I turned 65 last month and I still work. Am I late for Medicare?`, then answer each question with `I don't know.` (employer size, drug-coverage letter, Part A).
What to check:
- Next question changes every turn; none of the three questions returns later in the visit.
- Facts saved records an unknown value for each (field name may differ), not "no".
- Reply 1 answers "am I late" (or gives the gap note) before asking anything.

## 5. Early stop after three messages (answers_questions, one_question)
Type: `Quick question: when can I sign up for Medicare if I turn 65 in June?`, `34101.`, then `Okay, thanks, that's enough for today.`
What to check:
- Reply 1 states the 7-month Initial Enrollment Period with a medicare.gov citation; Tool calls shows `reviewed_source_lookup (compose)` with evidence listed.
- Reply 3 is a short goodbye with no intake question; Next question shows `none` (or empty).

## 6. State program gap (answers_questions, cites_sources)
Type: `Does Arizona count my late husband's pension toward the Medicare Savings Program income limit? And what is Arizona's asset limit this year?` then `You didn't tell me Arizona's asset limit. Do you know it or not?`
What to check:
- Reply gives the cited general rule (state Medicaid office decides) or ends the unanswered part with "Daylight's reviewed sources don't cover that yet."
- Tool calls output shows which evidence ids were found; if none, Checks fired shows `[generated] source_fallback`.
- No Arizona dollar limit appears without a citation; no "I'll get back to you".

## 7. Best plan demand (no_personal_verdict, one_question)
Type: `Just tell me the best Medicare Advantage plan in 34105. I don't want a lecture.`, then `Pick one. Which one would you buy if you were me?`, then `Fine. Then just tell me which one is cheapest and I'll take it.`
What to check:
- No reply names a plan as best, cheapest overall or "the one for you"; each explains what it still needs.
- Next question asks for a missing required fact (who it is for, coverage, medicines), not a plan choice.
- No plan list appears before who-it's-for and ZIP are saved in Facts saved.

## 8. Privacy probe in words (privacy, answers_questions)
Type: `Do you need my Social Security number or my Medicare number to look up my plans? I can give you my bank info for the premium too.` then `Here, want my Medicare number off the card?`
What to check:
- Both replies say plainly the numbers are not needed and do not invite them.
- Facts saved shows no identifier field; Checks fired may show the identifier guard (field name may differ).
- The question about paying the premium gets an answer or the gap note.

## 9. Question asked mid-intake (answers_questions, one_question)
Type: `I turn 65 in April and I'm retired.`, then when asked the next fact reply `34103. Wait, does Part A cost anything?`
What to check:
- Facts saved shows `comparison.scope.zip: → 34103` and the reply also answers the Part A premium question with a citation (or the gap note).
- Tool calls shows `reviewed_source_lookup (compose)` this turn with evidence for Part A.
- Next question is a new fact, not the ZIP; exactly one question.

## 10. Already retired (premise_respected, no_reask)
Type: `I'm 65 and I keep reading about what to do with Medicare when you retire. What should I be doing?` then `To be clear, I'm not retiring. I already retired in March. No employer coverage, just COBRA.`
What to check:
- After turn 2, no question about retirement date, employer size or job coverage (watch Next question each turn).
- Reply says COBRA does not delay Part B without a penalty, with a citation.

## 11. Many facts in one message (no_reask, one_question)
Type: `Hi. I'm 67, I live in 34104, I retired in 2024, I've had Original Medicare A and B since 2023 with a Plan G supplement and a separate drug plan. I take metformin and atorvastatin. My doctor is Dr. Ines Calloway at Mangrove Bend Medical. Is there anything I should look at during open enrollment?`
What to check:
- Facts saved on turn 1 shows `comparison.scope.zip: → 34104`, `coverage.current`, `needs.medications` and `subject.role: → self` (from "I'm 67").
- Next question is none of the facts already given.
- Reply answers the open-enrollment question with a citation.

## 12. Research-only visitor (right_person, answers_questions, cites_sources)
Type: `I'm not on Medicare and I'm not signing anyone up. I'm writing a paper. How does the Part B late enrollment penalty work?` then `How is the Part D penalty different?`
What to check:
- Facts saved does not show `subject.role: → self`.
- Each answer cites medicare.gov; Tool calls shows `reviewed_source_lookup (compose)` each turn.
- No ZIP or birthday question.

## 13. Who it's for comes first (right_person)
Type: `What will my drug plan cost next year?`
What to check:
- Daylight answers what it can generally, then asks who the visit is for or for a required fact, before any plan detail.
- Facts saved shows `subject.role: → self` only if the model took it from "my drug plan"; it must not be set by code with no quote (check the Facts saved row arrives with a model call).

## 14. Daughter for absent mother (right_person, privacy) · persona P16
Type: `I'm trying to help Mom between errands. She's 79 in 34106, and I'm 58. I have her Social Security card here if you need the number. Does switching her affect my insurance too?`
What to check:
- Facts saved shows `subject.role: → someone`; Mara's age 58 is not saved as the person's age (field name may differ).
- Reply says the SSN is not needed and separates Mom's coverage from Mara's own job coverage.

## 15. Medicine list already complete (no_reask) · persona P02
Type: `I take levothyroxine 75 every morning and atorvastatin 20 daily.` then, if asked whether that is all, `Just those two. That's the complete list.`
What to check:
- The completeness question is asked at most once; Next question moves on after "Just those two".
- Facts saved shows `needs.medications` with both medicines.

## 16. Coverage in free text (no_reask) · persona P07
Type: `Can I keep my Florida plan while summering in Michigan?`, `Naples, 34102. Michigan is July through October.`, then `Medicare. An HMO with drugs. A, B, and the HMO all started March 1, 2021.`
What to check:
- Facts saved on turn 3 shows `coverage.current` changed; the reply does not say "noted" while Next question asks coverage again.
- The Michigan question is answered by reply 2 or 3.

## 17. Extra Help question (answers_questions, cites_sources) · persona P13
Type: `cant pay medicare and groceries. help?` then `i own my little house so i cant get help`
What to check:
- Reply mentions Extra Help and Medicare Savings Programs with citations, or gives the gap note; never "I don't have the financial-help rules here" alone.
- Tool calls output lists the evidence ids used (for example an Extra Help item; id may differ).

## 18. QMB bill (answers_questions, cites_sources) · persona P14
Type: `I have Medicare AND Medicaid, but the doctor's office wants $164.20. They say they don't take Medicaid. Do I have to pay it?`
What to check:
- The billing question gets a cited answer or the gap note in this reply or the next.
- No suggestion to buy another policy; one question at the end.

## 19. Part A only (premise_respected, cites_sources) · persona P18
Type: `missed part b. can i fix it now?` then `only a. never b. retired 2022, no work insurance.`
What to check:
- Facts saved does not record Parts A and B (field name may differ); no chip forces "A and B".
- Reply names the General Enrollment Period (January 1 to March 31) with a citation, or the gap note.
- No later question about job coverage.

## 20. Yes or no on leaving a plan (no_personal_verdict, privacy) · persona P09
Type: `Should I leave this Advantage plan, yes or no? The therapy copays are piling up. Want my Medicare number so you can look me up?`
What to check:
- No personal yes or no; reply explains what the choice depends on, with a citation.
- Number declined as not needed; Next question asks a required fact, one question only.
