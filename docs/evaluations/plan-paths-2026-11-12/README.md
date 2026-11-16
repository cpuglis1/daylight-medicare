# Plan-path profiles · 2026-11-12 (16 profiles)

**D168 evaluation companion:** [Behavior-led complete journeys](../behavioral-journeys-2026-11-14/README.md)
adds reactive navigation, side questions, backtracking and goal-completion criteria.
This original corpus remains coverage/claim regression material; its fixed scripts
alone do not establish completed user journeys.


Sixteen fictional people for watching how someone moves through Daylight's journey (teach → settle the coverage path → see the plans for that path → Before you enroll), what they understand at the end, how Daylight's sorting (D147) answers them, and how the doctor, pharmacy and medicine checks (D146) treat real 2026 records.

**Understanding over evaluation.** The point of a run is a short account per profile, not a pass rate: where the person landed, which tabs they reached, what they could say back at the end, where they got stuck, and what the sorting and checks showed them. The answer keys stay so a content error is still caught.

Built from the Daylight Brain (02 UX playbook, 04 Data, 05 Pilot and validation, Decisions), the 2026-11-08 persona set, D147's method, D146's plan and foundation handoff, and the retained 2026 sources listed under "Real data". Nothing here was run against the advisor; no model calls were made.

## The profiles

| ID | Who | Typist | Age, ZIP | Path they land on | Real-data checks | What it probes |
|---|---|---|---|---|---|---|
| PP01 | Marguerite Ollander | self | 64, 34104 | Medicare Advantage | Doctor, pharmacy, medicine | First-time enrollee; Dr. Shannon Wise has four offices and two sources disagree on the suite; asks for premium order |
| PP02 | Anita Valegro (was P08) | self | 72, 34105 | Medicare Advantage | Fictional doctor (negative control) | Calls her HMO a supplement; sorting will suggest the other path |
| PP03 | Gideon Varrow | self | 68, 34106 | Original + Medigap + Part D | Doctor (misspelled), out-of-region doctor, pharmacy, 2 medicines | Job coverage ended; ended coverage must not be captured as current |
| PP04 | Corinne Haddley | self | 66, 34102 | Original + Medigap + Part D | Doctor, independent pharmacy, medicine | Window closed; same sorting inputs as the Nov 12 live check |
| PP05 | Harlan Brightwell | daughter | 74, 34108 | Original + Medigap + Part D | — | Plan F holder; cost order may top a high-deductible letter |
| PP06 | Desmond Rell (was P09) | self | 65, 34108 | Original + Medigap + Part D | Fictional doctor (negative control), medicines incl. OTC | Trial right; identifier probe |
| PP07 | Evangeline Shor | self | 65, 34103 | Part D only | Pharmacy, 3 medicines | Breyna is on only 4 of 10 PDP lists; others list Symbicort or the unbranded inhaler |
| PP08 | Thaddeus Moorland | self | 70, 34105 | Part D only | — | No medicines, asks for 2027; the one profile where a Part D pick is allowed (on 2026) |
| PP09 | Nolan Fenwick (was P01) | self | 64, 34103 | Keep current or wait | — | Current job coverage holds the path suggestion |
| PP10 | Lila Norcombe (was P10) | self | 73, 34102 | Keep current or wait | — | Plan G holder tempted by a $0 ad |
| PP11 | Rosamund Peyl | self | 65, 34108 | Original + Medigap + Part D | Opted-out doctor, pharmacy, 2 medicines | Medigap's "any doctor who takes Medicare" ✓ is wrong for her internist |
| PP12 | Delphine Marchetti | self | 71, 34104 | Medicare Advantage | Pharmacy, 4 medicines, fictional doctor | Insulin cap vs Eliquis; preferred vs standard CVS; asks for drug-cost order |
| PP13 | Lionel Brandeis | self | 64, 34103 | Original + Medigap + Part D | 2 doctors + a same-surname distractor, 2 medicines | "Albagdadi" matches two real cardiologists; must confirm before checking |
| PP14 | Walter Brennick | self | 67, 34102 | Medicare Advantage | Doctor, pharmacy, 2 medicines | D91 r7 case; Wellcare 2026 listing vs NCH leaving Wellcare in 2027; a dentist with the same surname |
| PP15 | Ilse Varga | son | 71, 34103 | Part D only | Independent pharmacy, 5 items | Stoney's is in network for 3 of 10 PDPs; Ozempic needs approval everywhere; vitamin D isn't Part D |
| PP16 | Russell Thackeray | self | 65, 34102 | Undecided; investigate only when requested | 2 real doctors, 2 medicines | The November 12 owner test conversation, reproduced (D157): turned 65 November 8, on COBRA, neither Part A nor B; asks what is best for him four times. Carries the thirty inputs, the baseline measures and the done-when criteria in `reproduction` |

Outcome mix: Medicare Advantage 4, Original Medicare with Medigap and Part D 6, Part D only 3, keep current or wait 2, undecided 1. Ten profiles run real-data checks: six check real doctors, eight a real pharmacy, ten real medicines with RxCUIs. Four fictional doctors are negative controls. Two helpers type (PP05, PP15).

## What changed on November 12 (second pass)

- **Five new profiles (PP11–PP15)** built around the D146 checks.
- **Real people and places in four earlier profiles.** PP01's doctor is now Dr. Shannon Wise, PP03's Dr. Elizabeth Hidlebaugh (typed misspelled) plus a fictional Asheville doctor, PP04's Dr. Mark Speake; PP01, PP03, PP04 and PP07 now name real pharmacies. Openings and answer keys otherwise unchanged.
- **`expected_sorting` on every profile (D147).** The inputs the conversation should capture, and the expected path suggestion, top match or no-pick reason on each tab under method `daylight-tiered-v1-20261112`, plus what should change once D146 checks feed the method (`after_d146`). This replaces `expected_outcome.recommendation` and answers UX playbook issue 18.
- **Two deliberate disagreements.** PP02 and PP14 expect the person to choose Advantage, while the sorting will suggest Original Medicare on their doctors priority (it can't weigh health questions or givebacks). Record how the chat reconciles them.

## Real data: rules and sources

- **Real doctors appear only where the profile claims nothing the sources don't show.** Scenario facts about a doctor (a network departure letter, a membership fee) are either backed by a recorded source (PP14's NCH notice, from the D91 r7 case) or marked fictional in `ground_truth`. PP02's and PP06's doctors stay fictional because their scenarios assert network facts.
- **Fictional names are negative controls.** A correct result is "no match found" with a request for spelling or office, never a similar real doctor.
- **Evidence was read on November 12** from the repo's retained sources, read-only:
  - Doctors: L08 `wellcare-r5/providers.sqlite3` (Wellcare directories dated 09/23/2026; Humana directories dated 10/11–10/12/2026) and `original-medicare-r6` (Medicare clinician file 2026-10-02; opt-out file updated 2026-10-21).
  - Pharmacies: L07 `build-r1` network rows (71 drug-bearing Collier offerings) and `location-build-r4/Collier-pharmacies.json`.
  - Medicines: L05 `build-r3` basic formularies for the 10 PDPs plus Humana Gold Plus H1036-217, Wellcare Giveback H1032-198 and HumanaChoice PPO H5216-072.
- **The D146 foundation package** (`daylight_pilot_foundation_2026_r1`) binds these same sources; a new bound revision from the doctor or pharmacy work may legitimately differ. When it does, record the difference rather than calling either side wrong.

## Current expected outcomes — November 14, D166/D167

The current key uses `daylight-tiered-v3-20261114` with the discussion planner enabled.
The November 12 v1 descriptions below are historical context, not the current oracle.
A scenario’s proposed destination is a route to investigate, never authority to record
an actual choice. PP16 explicitly remains undecided after the original thirty inputs.
Predictable costs do not create a Medigap lean, trigger pricing intake or choose a tab.

- Existing MA/Medigap coverage holds automatic path suggestions. Keeping Plan G
  settles that component only; reporting a policy does not mean choosing to keep it.
- A drug-cost review in current MA stays on Advantage. A separate drug-plan review
  opens Original Medicare’s prescriptions step. Explicit links open the requested list,
  without routing back through A/B signup. General exploration opens the two paths.
- Exact products produce dated formulary observations. A confirmed outlet enables
  pharmacy participation observations; absence is unresolved, not an out-of-network finding.
- Supported estimates use one confirmed refill schedule and retail averages across plans.
  They can order comparable estimates within fit groups; unsupported estimates remain
  visible and unranked. Premium order and preferred pharmacy status do not prove the
  cheapest medicines. Drug estimates exclude medical costs and never authorize a pick.
- Unknowns, PA/quantity-unit/source holds and 2027 gaps remain visible. An OTC item
  cannot disappear from a reported list simply to make the cost comparison succeed.

The six-profile replay and its explicit limitations are in
[the November 14 packet](../../../audit-evidence/profile-replay-20261114/README.md).
The older `test_pp16_journey.py` intentionally remains legacy-surface regression
coverage; current planner acceptance is `test_profile_replay_20261114.py`.

## Running notes

- **Unscripted questions:** the tester answers briefly from `ground_truth`, in the persona's voice; "I'm not sure" if it isn't there.
- **Before a live run:** settle the test model (Brain Open questions C22), check `/api/status` (including `eval_recommendations`), run PP01 alone, then the rest.
- **Cost:** about $0.45–$0.55 per profile at 8–9 turns, so about $7–8 for fifteen, inside the $15 daily allowance shared across ports. Live runs need Chris's clearance.
- **Teach-back:** every profile ends with a say-back. Eleven contain a misconception the reply should correct; four (PP02, PP03, PP10, PP13) are correct and should be confirmed.

## What to record per profile

1. The path the person landed on, and the sorting's path suggestion (or no-pick reason).
2. Tabs reached, turns to the first tab, group counts and the top match on each tab.
3. Each doctor, pharmacy and medicine result against `checks`, with the evidence date shown.
4. Re-asks and off-path questions.
5. The teach-back: corrected, confirmed or missed.
6. Confusion points, in the person's words, and anything a participant could take as advice or a current offer (target: none).

## Files

- `profiles.json`: the sixteen profiles.
- `profiles.schema.json`: the contract.
- `validate.py`: offline checks (structure, ages from birth dates, pilot ranges, teach-back placement, path mix, identifier probe, real-data check coverage). From the repo root: `infrastructure/daylight-data/.venv/bin/python docs/evaluations/plan-paths-2026-11-12/validate.py`
- `validation.json`: the last validation report.
