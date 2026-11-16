# Build plan · Parts A and B as the foundation, two coverage paths · November 12, 2026

Status: proposed, for the owner's approval. Nothing here is built. It sequences [PLAN.md](PLAN.md) (D161, the specification) against the Brain and the pilot, and folds in the owner's direction from the evening of November 12. Where this and PLAN.md differ, the difference is listed in section 3.

## 1. What this plan was checked against

| Source | What it requires of this work |
|---|---|
| Brain, 01 Vision (D160) | "People should not have to become insurance experts…" A sound answer counts "even when it is to keep current coverage, wait or choose an option that pays Daylight nothing." Intent beats curriculum. Code decides; the AI explains |
| Owner, November 12 | "If someone uses us to educate themselves and enroll in part a and b only, then that is a success." The dashboard "may need creative thinking, like a three step decision… choose a and/or b, choose gap, choose d." "Always review the 2nd brain first. Always align plans." |
| Brain, 02 UX playbook | Easiest self-guided experience; plans visible as soon as possible; no question that changes nothing; say each thing once; check at three widths. Its journey line ("teach → settle the coverage path → see that path's plans → Before you enroll") predates D161 and needs Parts A and B put first |
| Brain, 05 Pilot | Sessions November 17 to December 4; capabilities agreed at the November 16 checkpoint; nothing sold, no one enrolled; must-pass: no material error shown, no one takes the 2026 hypothetical as advice; no saved profiles; $100 model budget |
| Repo D157 (today) | Timing card, recorded coverage path, two-path card with listed ranges, 24-hour visit. Live baseline: the two paths with amounts at input 5, Medigap prices at input 11 |
| Repo D158, D159, D162 | 40 general Medicare facts accepted for education on :8895; 31 more candidates and 16 enrollment situations indexed and **not** accepted; the enrollment rule set (L13) is not accepted for personal deadlines or penalties |

## 2. The product shape

**Daylight always knows three things and shows them in the chat and on the plans pages:** what coverage the person has, what is still unresolved, and the next useful action.

**Six finishes, all of them success:** Parts A and B only · Original Medicare with a Medigap policy and/or Part D · Medicare Advantage · keep current coverage · wait, with the date to come back · not sure yet, with the one thing that would settle it.

**The dashboard is three decisions,** each ending in done, not needed, keep what I have, or decide later:

| Step | Original Medicare | Medicare Advantage |
|---|---|---|
| 1 | Parts A and B: in place, pending, next action and date | The same, shared |
| 2 | Your share of medical costs: Medigap, existing coverage, or none | Choose a plan |
| 3 | Prescriptions: Part D, existing coverage, or none | Check that plan's drug coverage |

A summary of the three answers stays in view. A person who only needs drug coverage opens at step 3.

## 3. Where this differs from PLAN.md

1. "Parts A and B only" is an explicit finish with its own summary, not the absence of a supplement.
2. The dashboard is three decisions, not sections inside a tab.
3. The tabs do not change before the pilot (section 4).
4. The multi-day return ("I applied last week") is after the pilot, because the pilot has no saved profiles and a visit lasts 24 hours.
5. Handoff H5 (path amounts) is no longer a dependency; the browser fills the ranges.

## 4. Phases

Each phase has a fixed list. Anything found along the way is written down and brought to the owner, not built.

### Phase 0 · Align · November 13
| Deliverable | Owner |
|---|---|
| Brain: playbook journey and north-star measures updated for D161; this plan linked; decisions recorded | Claude |
| Statement list: every new sentence a person would see in phase 1, each with its source, marked accepted (D159), candidate (D162) or new. The owner signs or cuts each one | Claude drafts, owner signs |
| Contract tests for the enrollment record, written failing | Claude writes, record's owner makes them pass |

### Phase 1 · The foundation, before the pilot · build November 13 to 15, on :8895 first
| Deliverable | Owner | Done when |
|---|---|---|
| Enrollment record v1, derived from what the conversation already collects: each part as active, pending, expected automatically, needed or unknown; the six finishes; dates marked estimated or reported | Backend (see decision 3) | Contract tests pass; stories 1, 3, 6 and 8 of PLAN.md section 7 pass offline |
| Status line and next step, one compact line in the chat and above the existing three tabs ("Part A: not yet · Part B: not yet. Next: sign up through Social Security by February 28, 2027") | Claude | Seen at three widths; first plan still above the fold on desktop |
| Sign-up route card: where and how to apply, what to have ready; no identity numbers asked for | Claude, from signed statements | One card, once; sources shown |
| "Parts A and B only" on the two-path card and as a recorded finish | Claude | PP16 variant ends there with a summary |
| Same-visit update: "I applied" or "I have Part A now" changes the status line | Claude with the record | Offline story; estimated never shown as confirmed |

Scope held for the pilot: ordinary turning 65, already enrolled, Part A only adding Part B, and COBRA. Employer coverage with an HSA, missed windows, disability, railroad and penalties get the accepted general explanation and the official place to confirm, never a personal date.

**November 16 checkpoint:** the owner decides what participants see, from a cleared live run and the three-width screens. If phase 1 is not clean, sessions run on today's build.

### Phase 2 · During the pilot · November 17 to December 4
No participant-visible change except a must-fix. Built and reviewed on :8895 only: the three-step dashboard using the existing plan panels; statements for employer size, HSA and missed windows taken through sign-off; the design for optional saved progress. Pilot sessions are tagged first decision or fall review, and note whether the person could say what coverage they have and what to do next.

### Phase 3 · After the go/no-go · from December 7
Switch the three tabs to the two paths with three steps. The multi-day return and status updates. Coordinated dates, costs and Before you enroll. All fourteen stories offline, three widths, then a cleared live run.

## 5. Rules that bind every phase

- Code computes every date and status; the model explains. A new sentence about Medicare needs a source and the owner's sign-off.
- The application itself happens at Social Security or the Railroad Retirement Board. Daylight never asks for an SSN, a Medicare number or a password, and never says an application was sent, approved or in effect unless the person reported it; reported is labelled reported.
- No personal deadline or penalty outside the accepted rules. Missing Medigap prices never steer toward Medicare Advantage. Every plan stays visible; commissions never enter the model or the sorting.
- :8895 first; :8894 changes only on the owner's release. One agent at a time in `alternatives/advisor-first/`. Live runs only when cleared.

## 6. Risks

| Risk | Handling |
|---|---|
| A pilot participant acts on a sign-up date Daylight computed | Phase 1 dates come only from the rule signed off today, labelled as estimates with the official source; anything else points to Social Security |
| Three days is short for a backend record plus front end | The status line can run on a thin record built from existing answers; the checkpoint can hold the change back |
| Most pilot participants may already be on Medicare | The status line then reads "Parts A and B: active" in one line and stays out of the way |
| Scope growth, as on November 12 | Fixed lists per phase; findings are reported, not built |

## 7. Measures

Added to the playbook's three: can the person say what coverage they have and what their next step is · inputs before the status line is right · runs that end in one of the six finishes · any reply that states an estimated date as confirmed (target zero).

## 8. Decisions needed from the owner

1. **Approve the phases,** in particular that the tabs change after the pilot.
2. **May pilot participants see sign-up guidance** (status, the official route, the window computed from their birthday month)? It is real, not hypothetical, so it sits outside "2026 hypothetical". Recommended: yes, as explanation with the official source, never as a personal deadline beyond the signed rule.
3. **Who builds the enrollment record.** It is backend. Recommended: Codex builds it against Claude's contract tests; if Codex is not available by November 13, Claude builds a thin version inside the conversation layer and Codex replaces it.
4. **Optional saved progress** for the return visit: design in phase 2, release after the pilot. Confirm.
5. Still open from earlier: the wording of the twelve plan-letter lines and the Part B premium sentence.
