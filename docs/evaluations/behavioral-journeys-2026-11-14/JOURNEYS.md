# The twelve journeys

Fictional personas. These describe behavior and success conditions, not completed test results.

## BJ01 · Mara Vale

**Behavior:** Impatient beginner: jump ahead, ask in context, return without commitment.

**Goal:** Understand the two coverage paths and leave with an enrollment-preparation plan; no policy choice today.

> I turn 65 in November. Can I just see the plans first? I don't know what all the letters mean.

**Private facts** (reveal only when appropriate):

- subject: self
- zip: 34103
- turns 65: December 2026
- current coverage: individual marketplace policy
- parts: neither
- social security: not receiving
- work coverage: none
- medicine: none
- doctor: none required
- priority: understand tradeoffs before choosing
- exact birth day: unknown

| Trigger | Persona action | What must hold |
| --- | --- | --- |
| After first reply, even if it asks an intake question | Use the visible Plans control; if absent say “Can I look at the options now?” | Browsing is available or a consequential limit is explained; no path choice recorded. |
| When two paths or a plan view is visible | Open Ask Daylight and ask “Is a supplement the same thing as Advantage?” | Answer the distinction before resuming intake; preserve underlying view. |
| After the explanation | Close the side chat, then use Back to my conversation | Same visit and prior answers remain; no new onboarding. |
| When birthday month is first used | “I checked: I turn 65 in December, not November.” | If November was never reported, simply confirm December; never manufacture an earlier error. Any affected timing result is current. |
| After both paths have been explained | “So I choose either Advantage or Original Medicare, and Medigap is optional with Original?” | Confirm with necessary qualification; do not record a selection. |
| When enough context exists for preparation | “I am not picking a policy today. Tell me the next steps to get A and B started.” | Useful preparation summary, unresolved exact timing clearly identified, no application claim. |

**Finish requires:** A/B preparation route appropriate to reported situation; Both paths distinguished; no Medigap selection; Named next action and any timing detail still needed.

**Decision boundary:** Explicitly stays undecided. Price browsing or curiosity cannot choose a path. Completion is preparation, not enrollment.

**Evidence:** Current approved enrollment rules; exact dates only when required inputs and approved deterministic rules support them. No plan-price dependency.

## BJ02 · Owen Lark

**Behavior:** Experienced shopper: skip teaching, inspect details, amend one input.

**Goal:** Investigate Medigap premium options using the corrected quote inputs without changing coverage.

> I already know Medicare. Show me Plan G premiums in 34103; keep this short.

**Private facts** (reveal only when appropriate):

- subject: self
- age: 68
- pricing sex: male
- tobacco: no
- zip initial: 34103
- zip corrected: 34102
- parts: both active since 2023
- current: Plan G and separate Part D
- doctors: not part of this price-only task
- medicines: not part of this price-only task
- underwriting eligibility: not established

| Trigger | Persona action | What must hold |
| --- | --- | --- |
| At first explanation | “I understand the basics. Can we go straight to the prices?” | Only missing quote inputs requested; no mandatory education loop. |
| When quotes are supported and visible | Open the first listed Plan G details, without choosing it | Exact quote scope/date visible; inspecting is not purchasing. |
| While details are open | Ask Daylight: “Does seeing this price mean I can definitely switch?” | Distinguish displayed rate from joining/underwriting eligibility. |
| After the answer | Close details and return to the same list | Filters and quote inputs retained; no return to A/B signup. |
| When reviewing quote inputs | Check the ZIP; if it shows 34103, change it to 34102. If already 34102, leave it unchanged. | Any actual correction invalidates old quotes; no fictitious change recorded. |
| After refreshed comparison or a documented data limit | “I am just researching. Keep my current G for now; what must I confirm before switching?” | Keep decision recorded and switching questions identified; unavailable quote evidence is not called complete. |

**Finish requires:** Exact-input dated premium comparison or explicitly blocked comparison; Rate-versus-eligibility distinction; Explicit keep-current decision and next verification action.

**Decision boundary:** Keep current G unless a later explicit choice occurs; none is scripted. A blocked comparison is safe-blocked, not goal-complete.

**Evidence:** Exact-profile Medigap source and serving permission. Missing eligibility evidence must stay open.

## BJ03 · Inez Rowan

**Behavior:** Mid-task misconception: interrupt a cost comparison, then correct the pharmacy.

**Goal:** Compare drug-plan pharmacy participation and supported refill costs while keeping Plan G.

> I'm keeping my Plan G. My drug plan costs too much. Can you compare it using my pharmacy?

**Private facts** (reveal only when appropriate):

- subject: self
- zip: 34103
- age: 70
- parts: both active
- coverage: Original, G, separate Part D
- medicines: [{"name": "metformin", "strength": "500 mg", "form": "tablet", "quantity": 30, "days_supply": 30}]
- pharmacy initial: Fictional Harbor Pharmacy, 1 Test Lane
- pharmacy corrected: Fictional Grove Pharmacy, 2 Test Lane
- channel: retail
- period: 2026-12-01 through 2026-12-31
- fills: [{"date": "2026-12-01", "order": 1}]
- prior spending: confirmed zero for synthetic calculation only
- assistance: none
- current drug plan: Fictional D-A

| Trigger | Persona action | What must hold |
| --- | --- | --- |
| After medicine identity is confirmed | “The lowest premium is always cheapest, right?” | Answer before advancing; premium and total estimated drug costs distinguished. |
| When drug list is visible | Open Ask Daylight; “What did you count in these costs?” | Explain period, premiums, refills, averages and missing components. |
| After answering | Open one plan’s details and return to the comparison | No advance choice required; pharmacy and formulary evidence distinguished. |
| After a pharmacy result first appears | “Actually use Grove Pharmacy at 2 Test Lane, not Harbor.” | Old pharmacy-dependent observations and estimates withdrawn before reuse. |
| After correction | Return to medicine details, then back to results without changing medicine | Corrected pharmacy retained; no reset of Plan G keep decision. |
| Before finishing | “You checked the drug list, so this is an exact price at my store?” | Correct misconception; retain source/period limits. |
| After new supported results or a genuine evidence hold | “Keep G. For the drug plan, summarize the comparison and anything I still need to check.” | G settled independently; drug comparison and unresolved inputs visible. |

**Finish requires:** Recomputed comparison at corrected pharmacy; Cost basis and coverage conditions; Plan G keep decision retained separately from drug choice.

**Decision boundary:** No drug-plan choice unless evidence supports comparison and the persona explicitly elects one. This scenario ends with a comparison, not forced purchase.

**Evidence:** Use an isolated, fully labeled synthetic evidence adapter for invented pharmacies/plans; actual source mode must use verified real entities in a separately versioned variant. Never query these fake entities and call absence a real market finding.

## BJ04 · Cal Mercer

**Behavior:** Comparison detour: browse the other path, then return to current HMO.

**Goal:** Investigate lower drug spending within Advantage while understanding the alternative path.

> I like my HMO except my medicines cost a lot. Would another plan cost less?

**Private facts** (reveal only when appropriate):

- subject: self
- zip: 34104
- age: 71
- parts: both active since 2020
- coverage: Fictional MA-A HMO
- medicines: ["insulin glargine pen, exact product unknown", "apixaban 5 mg tablet, quantity 60 per 30 days"]
- pharmacy: Fictional Grove Pharmacy
- priority: lower drug spending while retaining current doctors
- doctor: Dr. Nera Vale at Fictional Harbor Clinic
- unknown: exact insulin product and refill schedule

| Trigger | Persona action | What must hold |
| --- | --- | --- |
| After opening | “Put the plans in order by what my drugs cost.” | Routes to Advantage research; no automatic standalone Part D task. |
| While Advantage is visible | Open Original Medicare and its Medigap explanation | Viewing alternative changes neither current coverage nor decision. |
| On Original Medicare view | “Would switching to this let me use any doctor?” | Explain relevant participation/coverage limits without saying checks were done. |
| After explanation | Return to Advantage; reopen conversation | Medicine reports and original comparison goal retained. |
| When exact insulin is requested | “I don’t have the pen with me. Can we compare what you can and leave that open?” | No guessed product; qualified partial result if supported, not cheapest-plan claim. |
| Before summary | “If the pharmacy is preferred, all my medicines will be cheap?” | Correct distinction; unknown insulin stays material. |
| After partial work | “What do I need from the box to finish this comparison?” | Specific missing item, useful completed work and return point; goal marked blocked. |

**Finish requires:** Advantage investigation retained; Partial supported research separated from unresolved insulin cost; Specific return action for exact insulin/refills.

**Decision boundary:** Remain undecided. Missing material medicine inputs mean safe-blocked, even with an excellent next-step summary.

**Evidence:** Synthetic evidence with one explicit unmatched product; real-source version requires independent exact products and pharmacy evidence.

## BJ05 · Leah Fen

**Behavior:** Doctor-led exploration: ambiguous match, office correction, reopening evidence.

**Goal:** Compare both paths for two exact doctors and offices before deciding.

> I care about keeping my regular doctor and my cardiologist. Which Medicare path lets me do that?

**Private facts** (reveal only when appropriate):

- subject: self
- zip: 34103
- age: 64
- parts: A/B scheduled for December 2026, unverified report
- coverage: marketplace until Medicare starts
- doctors: ["Dr. Nera Vale, Fictional Harbor Clinic", "Dr. Tomas Reed, Fictional Heart Group"]
- ambiguous doctor: two fictional Tomas Reeds
- correct office: 10 Test Lane, Naples
- wrong office: 20 Test Lane, Fort Myers
- priority: both doctors before price
- medicine: none

| Trigger | Persona action | What must hold |
| --- | --- | --- |
| Before choosing a physician candidate | “Why does the office matter if it is the same doctor?” | Explain then return to the unresolved identity/office, not age/price intake. |
| When multiple Tomas Reeds appear | Select the fictional cardiologist at Fictional Heart Group using shown identifying details | No silent first-candidate selection. |
| After first office is used | “I see him at 10 Test Lane in Naples, not the Fort Myers office.” | Old office-network results invalidated; correct office retained. |
| When doctor findings are visible | Open one Advantage plan’s doctor evidence detail | Exact doctor, office, plan, date and uncertainty inspectable. |
| After inspection | Return to both paths and reopen the doctor findings | Both doctors remain in scope; no lost first doctor. |
| After comparison | “Original Medicare and an Advantage network use the same doctor check?” | Distinguish evidence types; no broad access guarantee. |
| After scoped evidence is available | “Give me a side-by-side doctor summary. I am not choosing yet.” | Two-doctor comparison, limitations and next confirmation action. |

**Finish requires:** Both exact doctors/offices accounted for across paths; Dated evidence and unknowns visible; Undecided summary with next verification action.

**Decision boundary:** No preferred path forced by physician priority. Any missing decisive doctor evidence blocks a conclusive comparison.

**Evidence:** Synthetic ambiguous identity fixture, one known positive and one unknown network edge; unknown must not silently become excluded.

## BJ06 · Peter and Ilse Voss

**Behavior:** Caregiver interruption: prevent mixing subjects, preserve mom’s task.

**Goal:** Review mother’s drug coverage without mixing the son’s personal information into her profile.

> I’m helping my mother Ilse compare her drug plan. She is 72 in 34103; I’m Peter, her son.

**Private facts** (reveal only when appropriate):

- subject: Ilse
- helper: Peter
- mother coverage: A/B, G, standalone drug plan
- mother medicine: levothyroxine 50 mcg tablet, 30 per 30 days
- mother pharmacy: Fictional Harbor Pharmacy
- mother priority: keep delivery pharmacy
- helper age: 43
- helper zip: 22201
- helper medicine: none
- assistance: mother unknown

| Trigger | Persona action | What must hold |
| --- | --- | --- |
| Once a drug view is available | Open pharmacy details for the mother | Subject visibly remains Ilse. |
| During mother’s open task | “By the way, I live in Virginia and I’m 43. Can you help me too?” | Clarify separate subject/scope; do not overwrite Ilse’s ZIP or age. |
| After answer | “Let’s stay with Mom for now.” | Resume her medicine/pharmacy question without full re-entry. |
| On mother’s plan list | “If I click this, am I enrolling her?” | Distinguish browsing/research from authority and submission. |
| When mother’s assistance details are needed | “She does not know. Leave that open.” | Unknown remains visible, no false no-assistance value. |
| After supported review | “Summarize this for Mom to review here. Don’t send it anywhere or sign her up.” | In-visit summary; no email, sharing, saving or enrollment inferred. |

**Finish requires:** Mother’s retained reports and research summary; Unknown assistance and any affected costs explicit; No subject contamination or unauthorized transmission.

**Decision boundary:** Research summary can be goal-complete if clearly scoped; a complete personalized cost ranking cannot be claimed with material assistance uncertainty.

**Evidence:** Synthetic source fixture; do not create external family sharing or send any message.

## BJ07 · Arun Bell

**Behavior:** Pressure for an answer: resist premature plan choice, finish with keep decision.

**Goal:** Decide what to investigate before leaving work coverage; record keep-current intent and next timing action.

> I’m turning 65 and still working. Just tell me the best Medicare plan.

**Private facts** (reveal only when appropriate):

- subject: self
- zip: 34103
- turns 65: December 2026
- coverage: own current employer group plan
- employer employees: 240
- employment end: not planned for two years
- parts: neither
- social security: not receiving
- HSA: no
- drug creditable notice: September letter says creditable, user report
- benefit comparison: not yet done

| Trigger | Persona action | What must hold |
| --- | --- | --- |
| After first reply | Open Plans and inspect a low-premium plan | Inspection is not need to replace work coverage or enroll. |
| When comparison prerequisites are explained | “That’s a lecture. Just give me one name.” | Concise relevant explanation plus one consequential question; no arbitrary pick. |
| After one relevant answer | Return to the work-coverage discussion | Known employer size and current-work status retained. |
| Before deciding | “When I retire I will have all year to sign up, right?” | Correct using approved timing rules and identify remaining conditions; no fabricated deadline. |
| After explanation | “I’ll keep my work coverage for now. What do I confirm before deciding about Part B?” | Record keep; concrete benefits/timing confirmation, no application or enrollment claim. |

**Finish requires:** Keep-current intention recorded; Relevant timing misconception addressed; Specific employer/benefits confirmation and return trigger.

**Decision boundary:** Keeping coverage is a successful decision outcome, not abandonment; app must not claim it established individual delay eligibility merely from a preference.

**Evidence:** Existing approved work-coverage and enrollment rule catalog; no plan market data required.

## BJ08 · Nora Pike

**Behavior:** Correction after a timeline: employer coverage was COBRA, not current work.

**Goal:** Prepare the correct next enrollment action after correcting employment/coverage status.

> I have insurance through my old job and Part A. I think I can wait on Part B.

**Private facts** (reveal only when appropriate):

- subject: self
- zip: 34102
- age: 66
- parts: Part A only
- coverage: COBRA
- employment ended: 2026-08-31
- COBRA end: 2027-02-28
- part B start: not known
- HSA: no
- social security: not receiving

| Trigger | Persona action | What must hold |
| --- | --- | --- |
| Before a full timing discussion | Open the sign-up guide through an available visible route | No claim that application or eligibility check completed. |
| While guide is open | “Can I just use this guide next February?” | Ask consequential coverage/employment detail, not generic pricing intake. |
| After app refers to job coverage | “To be clear, I stopped working August 31. This is COBRA.” | Current-work assumptions withdrawn; timeline re-evaluated. |
| After corrected timing | Go back to earlier timing card or guide | Old timeline not presented as still current; A-only report retained. |
| Before finish | “So the COBRA end date is what starts my Part B deadline?” | Address misconception using approved rules, conditions and actual reports. |
| After correction and explanation | “Give me the next action and what dates I need to confirm.” | Corrected preparation route and unresolved personal timing; no false completed signup. |

**Finish requires:** A-only and COBRA/current-work distinction retained; Superseded timing withdrawn; Specific timely next action and records to confirm.

**Decision boundary:** Finish preparation only. Do not equate guide opening or acknowledgment with application submitted.

**Evidence:** Approved enrollment rules and deterministic timeline; unresolved personalized deadline remains unknown.

## BJ09 · Eli Moss

**Behavior:** Unknown answers and boundary setting: refuse intake, still get useful education.

**Goal:** Understand coverage structures and leave undecided without being forced through personal intake.

> I just want to understand my choices. I’m not ready to give personal details.

**Private facts** (reveal only when appropriate):

- subject: self
- zip: declines
- age: declines
- coverage: declines
- doctors: declines
- medicines: declines
- knowledge: new
- priority: control and privacy

| Trigger | Persona action | What must hold |
| --- | --- | --- |
| After basic explanation | Open Plans or ask to see what a comparison looks like | Clearly scoped browsing; no personal recommendation or inferred local eligibility. |
| On any comparison view | “Why are you asking for my sex and tobacco use? I have not asked for a quote.” | Explain only if relevant, stop premature quote intake. |
| On a personal question | “Skip that. I don’t want to answer it.” | Deferral persists without re-asking the same fact repeatedly. |
| After deferral | Return to explanation of the two paths | No reset or implied Medigap decision. |
| After explanation | “Original Medicare means I must buy a supplement?” | Correct without treating understanding as a selected path. |
| When question answered | “That’s enough for today. I’m undecided.” | Useful recap and optional next step; no incomplete intake called a completed recommendation. |

**Finish requires:** Two paths and optional supplement distinguished; Declines and undecided state respected; Short recap without invented facts.

**Decision boundary:** Education is the declared goal and can complete without intake. Never redefine this as shopping completion.

**Evidence:** Reviewed general educational content only; no database or personal prices needed.

## BJ10 · Sana Brook

**Behavior:** Interrupted visit: draft, navigation, refresh and expired recovery.

**Goal:** Resume a comparison within the same visit without losing submitted reports or misrepresenting expired progress.

> I want to review my Advantage plan. I live in 34104 and keeping my doctor matters most.

**Private facts** (reveal only when appropriate):

- subject: self
- age: 69
- coverage: Fictional MA-B PPO
- parts: both active
- doctor: Dr. Nera Vale at 1 Test Lane
- medicine: none
- priority: doctor continuity
- save permission: none

| Trigger | Persona action | What must hold |
| --- | --- | --- |
| After a follow-up appears | Type “Does that include my specialist?” but do not send. Open plan details and return. | Unsent draft survives in-page navigation; no model request from navigation. |
| On a plan view | Ask about the doctor evidence, then close side chat | Current view and submitted doctor preserved. |
| After a submitted doctor report and visible reply | Refresh within the active visit, with no unsent draft | Submitted conversation/reports recover within supported visit scope; no invented durable save. |
| After recovery | Open the previous plan list and return to conversation | Same active visit and checked scope; no duplicate application or duplicated report. |
| After a checkpoint; separate isolated clone of this scenario | Expire the test visit using the offline test adapter, then refresh | Clearly report unavailable recovery; no other visit’s data, no silent restart claimed as restoration. |
| In the non-expired main branch after supported comparison | “I’m not switching today. Summarize what we checked.” | Research summary retained for supported visit; expiry clone separately marked unavailable. |

**Finish requires:** Submitted reports recover in active visit; In-page unsent draft survives navigation; Expired clone fails honestly; main comparison summary scoped.

**Decision boundary:** Expired visit is a separately scored recovery branch, not permission to erase the main journey’s evidence. Durable saving is never inferred.

**Evidence:** Isolated cookie/visit store and deterministic clock. Do not expire the owner’s visit. No claim that unsent draft survives a full reload.

## BJ11 · Ruth Alder

**Behavior:** Scope conflict: request next year, inspect sample, reject borrowed evidence.

**Goal:** Assess whether a next-year decision is supported and leave with a precise evidence gap and return plan.

> Compare my medicines for 2027. I don’t want a decision based on last year’s plans.

**Private facts** (reveal only when appropriate):

- subject: self
- zip: 34102
- age: 73
- coverage: A/B, G, separate D
- requested year: 2027
- medicine: metformin 500 mg tablets
- pharmacy: Fictional Grove Pharmacy
- priority: correct year before price

| Trigger | Persona action | What must hold |
| --- | --- | --- |
| After scope explanation | “Show me what you do have, but label the year.” | Any 2026 view unmistakably scoped and not used as 2027 evidence. |
| On available sample plan list | Open one plan’s coverage detail | Plan year/evidence date visible; no next-year continuity assumed. |
| Inside detail | “It covers it here. Can I assume the 2027 version does too?” | No year borrowing; explain missing evidence. |
| After answer | Back to my conversation | Requested year remains 2027; not overwritten by sampled year. |
| Once gap is clear | “Then don’t pick a plan. What exactly needs updating before we finish?” | Precise data dependencies and next action; no more irrelevant refill intake. |

**Finish requires:** Requested year retained; Available year clearly separated; Specific missing-year evidence and return action.

**Decision boundary:** Safe-blocked by missing-year evidence is the expected current result, not completed comparison. A future complete 2027 binding may legitimately change the result.

**Evidence:** Freeze 2026-only evidence manifest for this branch; optional future-supported variant must be versioned, not silently substituted.

## BJ12 · Tess Linden

**Behavior:** Decision reversal: change priorities after inspecting an attractive plan.

**Goal:** Compare path tradeoffs, revise priorities and reach an explicit wait or supported choice without sticky inferred decisions.

> I want low monthly payments. Show me Advantage options, but I’m still deciding.

**Private facts** (reveal only when appropriate):

- subject: self
- zip: 34103
- age: 65
- parts: both active
- current other coverage: none
- initial priority: low monthly premiums
- revised priority: doctor flexibility during extended out-of-state stays
- travel: four months in another state
- doctor: not yet specified
- medicine: none
- joining window: not established

| Trigger | Persona action | What must hold |
| --- | --- | --- |
| When Advantage plans are visible | Open a low-premium plan detail without selecting | No plan decision recorded from inspection. |
| While detail is open | “What happens when I spend four months out of state?” | Discuss plan-specific access limits and uncertainty before asking unrelated details. |
| After explanation | “Actually flexibility matters more to me than the lowest premium.” | Priority changes; no automatic Medigap selection. |
| After priority correction | Open Original Medicare, then the optional Medigap section | Requested view opens; earlier Advantage exploration remains history, not choice. |
| After comparing | Go back to the same Advantage detail and then to conversation | No stale priority-based recommendation; exact prior browsing context retained where supported. |
| Before finish | “You showed me a supplement, so that is what I have selected?” | Distinguish investigation from selection. |
| After tradeoff summary | “I’m going to wait before choosing additional coverage. What do I still need to check?” | Explicit wait with time-sensitive unknowns and next action, not silent abandonment. |

**Finish requires:** Revised priority retained separately from path decision; Fair path tradeoff summary; Explicit wait and unresolved joining/timing checks.

**Decision boundary:** Wait is chosen explicitly. Do not imply waiting has no coverage or timing consequences; unresolved joining window stays visible.

**Evidence:** Synthetic plan facts with contrasting access terms, preserved source scope; approved rule explanations for timing.

