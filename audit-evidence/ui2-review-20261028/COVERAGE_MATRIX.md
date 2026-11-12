# 41-question coverage matrix · D79 UI2

Five fictional personas, nine HTTP journeys. Every turn passed real request/CSRF validation, the actual controller and report validation. Scripted AI output passed the actual strict language adapter; this does not establish model accuracy. Browser and live checks are recorded separately. No personal capability was released.

| ID | Question / check | Observed coverage | Evidence |
| --- | --- | --- | --- |
| T01 | What would you like help with today? | Asked / exercised | P1, P1-payer, P2, P2-browse, P3, P3-replacement, P4, P4-unknown, P5 |
| T02 | How familiar are you with Medicare? | Volunteered / reused | P5 |
| T03 | What ZIP code do you live in? | Asked / exercised | P2-browse, P3, P5, P3-replacement |
| T04 | When do you need Medicare coverage to start? | Asked / exercised | P1, P3, P5, P1-payer, P2, P3-replacement |
| T05 | What health coverage do you have now? | Asked / exercised | P1, P3, P5, P1-payer, P2, P3-replacement |
| T06 | Which doctors or hospitals would you like to keep? | Asked / exercised | P4, P5 |
| T07 | What prescriptions do you take? | Asked / exercised | P4, P5, P4-unknown |
| T08 | Will you need routine care away from home? | Asked / exercised | P5 |
| T09 | How would you prefer to balance monthly payments and costs when you get care? | Volunteered / reused | P3-replacement |
| T10 | What matters most when we compare your options? | Volunteered / reused | P3-replacement |
| RC01 | Who is this coverage for? | Asked / exercised | P3, P4, P5, P1, P1-payer, P2, P3-replacement, P4-unknown |
| RC02 | Where is your permanent home? | Asked / exercised | P5 |
| RC03 | Which year should we compare? | Asked / exercised | P2-browse |
| RC04 | Which Medicare parts do you have now? | Asked / exercised | P1-payer, P3, P5, P3-replacement |
| RC05 | When did Part B start? | Asked / exercised | P3, P3-replacement |
| RC06 | How did you first qualify, or expect to qualify, for Medicare? | Asked / exercised | P1-payer, P5 |
| RC07 | How do you get your A and B benefits now? | Volunteered / reused | P3-replacement |
| RC08 | What changed about your coverage? | Volunteered / reused | P2 |
| RC09 | Is this coverage from someone who is still working? | Asked / exercised | P1, P1-payer, P2 |
| RC10 | Does the employer have 20 or more employees? | Asked / exercised | P1-payer |
| RC11 | When did the job or coverage end? | Asked / exercised | P1, P2, P1-payer |
| RC12 | Do you have a written notice saying your drug coverage counts as creditable (as good as Medicare’s standard coverage), and has there been a gap? | Asked / exercised | P2 |
| RC13 | Could a change affect anyone else’s coverage? | Asked / exercised | P2 |
| RC14 | Are you or your employer adding money to an HSA? | Volunteered / reused | P1-payer |
| RC15 | For the Medigap option you want to explore, what coverage change or notice should we check? | Volunteered / reused | P3 |
| RC16 | Was this your first Medicare Advantage plan, when did it start, and did you have Medigap before? | Asked / exercised | P3 |
| RC17 | Are you replacing an existing Medigap policy? | Volunteered / reused | P3-replacement |
| RC18 | Do you currently receive benefits from any of these programs? | Asked / exercised | P4, P5 |
| RC19 | For the Special Needs Plan type you want to explore, what exact qualifying program or plan confirmation do you have? | Volunteered / reused | P5 |
| RC20 | Where will you need routine care away from home? | Asked / exercised | P5 |
| RC21 | What exact office and location should we use for each doctor or hospital? | Volunteered / reused | P4 |
| RC22 | What exact name, strength, form, and brand or generic preference should we use for each medicine? | Volunteered / reused | P4, P4-unknown |
| RC23 | For each medicine, what quantity, days supply, exact pharmacy and retail or mail order should we use? | Asked / exercised | P4 |
| RC24 | Is this given at a clinic or filled at a pharmacy? | Volunteered / reused | P4 |
| RC25 | Is there a monthly amount you want to stay under? | Asked / exercised | P5 |
| RC26 | Which military or veterans’ coverage do you have? | Asked / exercised | P5 |
| RC27 | Is there a coverage interruption you need help with now? | Volunteered / reused | P5 |
| RC28 | What should I correct about the specific detail we were discussing? | Integrity guard exercised | P3-replacement |
| RC11.C1 | When does the job-based health coverage end? | Within parent; exercised | P1, P2 |
| RC16.C1 | When did it start? | Within parent; exercised | P3 |
| RC16.C2 | Did you have Medigap before it? | Within parent; exercised | P3 |

“Volunteered / reused” means the substantive report or optional preference was accepted in the proper context without a routine follow-up. Internal entries do not become mandatory questions merely to make the matrix green. The three child entries are tested through their parent fields.

Remaining limits: the 14 representation/evidence gaps are unchanged; source-specific activation and independently accepted rules remain held. RC08 event-date and RC16 history preparation still use task-level routing rather than an accepted rule selecting exact necessary precision/history. RC21/RC24/RC19 source-specific candidate/method/qualification prompts cannot be exercised against an accepted integration because none is connected. Full source-backed decision behavior is therefore not claimed. Multiple-item parsing accuracy, physical keyboard and assistive-technology execution remain separate evaluations.
