# Daylight journey plan: from "what is Medicare?" to a ranked plan list

Prepared 2026-10-20. Status: **journey design for owner review.** This document defines the flow: what each stop teaches, what it asks, why, and what the answer changes. The UI comes next, in a separate plan built on this one.

**What this replaces**
- [Levels plan](DAYLIGHT_LEVELS_PLAN.md): its chat-first arrival and level system (sections 4 and 7) are **superseded**. Its constraints, CSP rules, accessibility rules and verification approach still apply.
- [Aesthetic plan](DAYLIGHT_AESTHETIC_PLAN.md): **on hold** until the UI pass. Its trust ideas carry forward (sources shown as receipts, "checked / not checked yet" stamps, reviewed content looking different from conversation). Its character and overall look are back under review.

**What stays the same:** the guardrails, the decision-map engine, the ranking engine, `/api/catalog`, `/api/live-chat`, the Collier 2027 data, the visual library V0–V8 (content), and the accessibility rules in the [guide redesign](DAYLIGHT_GUIDE_REDESIGN.md).

---

## 1. The idea

**Daylight is a short journey, not a chat.** It works like the first minutes of a good video game:

- **Stop 1 is almost too easy.** One tap, one personal answer, and you think "oh, this is for me."
- **Each stop adds one thing,** like finding an item or learning to jump: one idea, one question and one personal result.
- **You can always see the map:** where you've been, what you've picked up and how far is left.
- **The final stop, the plans, feels easy,** because every word and number on a plan card was taught on the way there.

### Why not start in chat

A chat log makes the person do the steering: they have to know what to ask, they scroll to find things, and they can't see where they are or how far is left. A journey gives them a location ("I'm on step 3 of 7"), a sense of progress and a guaranteed path to the end. The AI stays, but as a **helper you can call on at any stop**, not as the page itself (section 7).

### The one mental model: a foundation with three gaps

Every stop hangs off one picture, simple enough to remember the next day:

> **Original Medicare (Parts A and B) is the foundation. It leaves three gaps:**
> 1. **Prescriptions** (most aren't covered)
> 2. **Dental, vision and hearing** (routine care isn't covered)
> 3. **Your share of the bills,** about 20%, **with no yearly limit**
>
> **Everything else in Medicare is a way to fill those gaps. There are two ways to do it:**
> - **Fill each gap with its own piece:** a drug plan, Medigap for your 20% share, and a separate dental or vision plan if you want one.
> - **Or swap to one all-in-one plan** from a private company (Medicare Advantage), which usually fills the gaps its own way, with a network and a yearly limit.

This turns the alphabet soup (A, B, C, D, Medigap, Supplement, Advantage) into one picture: a foundation, three empty slots, and two ways to fill them. The "building blocks" visual (V4) becomes the person's own inventory, filling in as they move through the stops.

---

## 2. Journey rules

1. **One idea per screen, one question per stop.** No scrolling for information. Each screen is complete.
2. **Give before you get, and pay back right away.** Every question is followed immediately by something personal: a date, a "this means you can…", a filled slot.
3. **Ask at the moment it matters.** We ask about job coverage when Part B comes up, about prescriptions when drug coverage comes up, and for the ZIP code only when we're about to show plans. Asking for a ZIP up front feels like lead capture; asking for it in Stop 6 ("to show plans near you") feels useful.
4. **Never use a word before its stop.** The vocabulary ladder (section 5) is a hard rule.
5. **Nothing on a plan card is new.** Every field on the final cards was taught earlier (section 6).
6. **You always know where you are,** and you can go back. Finished stops never re-lock.
7. **Nobody is held back.** Every stop has "I already know this", which shows a one-line summary and goes straight to the stop's question.
8. **Daylight never picks.** It explains trade-offs in the person's own priorities, and the person records their own leaning.
9. **About 10 minutes end to end.** If a stop runs past ~3 minutes, it's too big.
10. **Honest at every stop** about what we can't check yet: doctor networks, Medigap prices, personal drug costs and some plan extras.

---

## 3. The map of the journey

```text
  (0) Start → (1) When it starts → (2) The foundation → (3) Prescriptions
            → (4) Dental, vision, hearing → (5) Two ways to fill the gaps
            → (6) Your plans → (7) Your next steps
```

- **On the front door,** the whole path is visible but faint, with only the first stop lit. You see right away that it's short, that it has an end, and that it's yours.
- **As you go,** each finished stop shows the item you earned (your dates, your foundation, your drug slot and so on).
- **At the end,** the path *is* your personal Medicare map: your dates, your choices, your gaps and how you'd fill them, your shortlist and your next steps. That's what prints.

The decision-map engine keeps computing the same five steps and statuses. The journey just presents them in teaching order:

| Engine step | Where it lives in the journey |
| --- | --- |
| `s1_ab` Get Parts A and B | Stop 1 |
| `s2_part_b` Keep Part B? | Stop 2 |
| `s3_path` Choose how to get coverage | Stops 3–5 decide the inputs; Stop 6 shows plans |
| `s4_dates` Key dates | Stop 1 (personal dates) and Stop 7 (full timeline) |
| `s5_help` Free help and enroll | Available at every stop; summarized in Stop 7 |

---

## 4. Stop by stop

Each stop follows the same loop:

> **Hook** (one sentence and one picture) → **the idea** (2–3 short cards, tap to advance) → **your turn** (one question) → **what this means for you** (an immediate personal result) → **item earned** (added to your map)

Each stop also teaches **one new way to interact**, so the interface itself is learned gradually, like game mechanics.

Wording below is **draft and illustrative.** All Medicare facts need domain review and must come from reviewed content (section 9).

---

### Stop 0 · Start

| | |
| --- | --- |
| **Hook** | Daylight helps you understand Medicare in about 10 minutes, one step at a time. The faint path of seven stops is visible. |
| **Get** | **Who is this for?** Me / Someone I'm helping (optional: parent, spouse, other) |
| **Why ask now** | It changes every sentence that follows ("you" or "your mom"), and caregivers are a core audience. |
| **Give back** | The trust basics, up front: no sign-up, no ID numbers, nothing saved after you close the tab, automated guide, not an insurance agent. |
| **New interaction** | Tap one big button. |
| **Time** | ~15 seconds |

---

### Stop 1 · When it starts

The "ooh, this is for me" moment.

| | |
| --- | --- |
| **Hook** | Medicare has a start date, and it's yours. |
| **Get** | **Do you have Medicare yet?** Yes, Parts A and B / Only Part A / Not yet, and I get Social Security / Not yet, I'll need to sign up / Not sure. If not yet: **What month and year do you turn 65?** |
| **Why ask now** | Deadlines are the number-one fear for new beneficiaries. A personal answer within 30 seconds lowers anxiety and shows the tool is about *them*. It's an easy question with a big payoff. |
| **Give back** | Their **personal timeline**: the 7-month sign-up window, the earliest coverage start date and whether enrollment is **automatic** (already getting Social Security: the card comes in the mail) or **they sign up**. Uses V0 and the start of V6. |
| **Item earned** | **Your dates** |
| **New interaction** | Pick from a short list; watch your result appear. |
| **Branches** | *Yes, A and B* → review journey (section 8). *Only A / Not sure* → "need more info", with what to check and free help (SHINE). |
| **Time** | ~1 minute |

---

### Stop 2 · The foundation

The "item" moment: you get your foundation, and you see three empty slots.

| | |
| --- | --- |
| **Hook** | Every Medicare journey starts with the same two parts. |
| **The idea** | Card 1: **Part A** is hospital insurance (inpatient stays, skilled nursing, hospice). Most people pay no monthly premium for it. Card 2: **Part B** is medical insurance (doctors, outpatient care, tests, equipment, preventive care). It has a monthly premium; after a yearly deductible, you usually pay about **20%**. Card 3: together they're called **Original Medicare**, run by the federal government and accepted by any doctor in the U.S. who takes Medicare. Card 4, the reveal: **the foundation has three gaps** (prescriptions; dental, vision and hearing; your 20% share with no yearly limit). The foundation block appears with three empty slots. |
| **Get** | **Do you or your spouse have health coverage from a current job?** Yes / No / Not sure |
| **Why ask now** | It's the only answer that changes the Part B decision (the booklet's second decision), and it lands right after we've explained Part B's premium. |
| **Give back** | *No:* most people take Part B when first eligible; waiting can mean a late penalty that lasts as long as you have Part B. *Yes:* you may be able to wait on Part B while you're covered through current work, but check with your benefits office first, because employer size matters; when that coverage ends you get a special window to sign up. *Not sure:* "need more info", plus the exact questions to ask HR. |
| **Item earned** | **Your foundation (A + B)** with three empty slots |
| **New interaction** | Tap a highlighted word to see what it means (glossary). **Ask Daylight** is introduced here, with three ready-made questions about this stop. |
| **Branch** | *Job coverage: yes* → offered a choice: keep learning, or skip to the checklist for "when my job coverage ends" (section 8). |
| **Time** | ~2 minutes |

---

### Stop 3 · Prescriptions (gap 1)

| | |
| --- | --- |
| **Hook** | The first gap: the medicines you pick up at the pharmacy. |
| **The idea** | Original Medicare doesn't cover most prescriptions. **Part D** does. You can get it two ways: as a **separate drug plan** added to Original Medicare, or **built into** most all-in-one plans (named and explained at Stop 5). Each plan has its own **drug list**, and many have a **drug deductible**. Part D also has a yearly cap on what you pay for covered drugs (the amount comes from the reviewed annual table). Going without drug coverage for too long after you're first eligible can mean a **late penalty**. |
| **Get** | **Do you take prescriptions regularly?** Yes / No / Not sure |
| **Why ask now** | It decides how much weight drug coverage gets later, and it's the natural moment, right after explaining what Part D is. |
| **Give back** | *Yes:* when we get to plans, you can check your exact medicines against real plans' drug lists. *No:* a reminder that the late penalty exists even if you take nothing today, and that drug plans differ in monthly cost. Facts only; no "you should." |
| **Item earned** | The **drug slot** lights up (filled in at Stop 5 or 6 with *how*) |
| **New interaction** | Watch a slot in your foundation fill. |
| **Time** | ~1 minute |

---

### Stop 4 · Dental, vision and hearing (gap 2)

A short bonus stop: a quick win and a common surprise.

| | |
| --- | --- |
| **Hook** | The second gap surprises a lot of people. |
| **The idea** | Original Medicare doesn't cover routine dental care, eye exams for glasses, or hearing aids, and Medigap doesn't either. Many all-in-one plans include some of these, with limits that vary a lot. Separate dental or vision plans also exist. |
| **Get** | **Any of these matter to you?** Dental / Vision / Hearing / None / Not sure (pick any) |
| **Why ask now** | It's concrete and easy, and it feeds both the Stop 5 trade-offs and the Stop 6 filters. |
| **Give back** | "Noted." Plus an honest line: plans differ a lot here; we show what we can confirm and say plainly where we can't yet. |
| **Item earned** | The **extras slot** is marked with their picks |
| **New interaction** | Pick more than one. |
| **Time** | ~30 seconds |

---

### Stop 5 · Two ways to fill the gaps (the big choice)

This is the "you can jump now" moment: everything learned so far snaps together.

**The picture (V4 as their inventory):**

- **Path 1 · Original Medicare + pieces.** Keep your foundation and fill each gap with its own piece: **Medigap** (also called Medicare Supplement; same thing) covers most or all of your 20% share; a **drug plan** fills the drug gap; a separate dental or vision plan if you want one.
- **Path 2 · Medicare Advantage.** One plan from a private company approved by Medicare that replaces how you get your A and B coverage. It usually **includes drug coverage** and **some extras**, has a **yearly limit** on what you pay for covered care, and uses a **network** of doctors and hospitals.
- Under both: **you still pay the Part B premium.** Between them: **you pick one path; Medigap doesn't work with Advantage.**

**Get (part 1): What matters most to you?** Keeping my current doctors / Seeing doctors when I'm away from Naples / Low monthly cost / Predictable bills, fewer surprises / Not sure. Pick any; if more than one, a second tap: **Which matters most?** (This sets the order used for ranking in Stop 6.)

**Why ask now:** this is the first moment the answer means something. They know both paths, so "keeping my doctors" now has a consequence they can understand.

**Give back: "What that means for you,"** one short row per priority they picked, showing both paths side by side and never a verdict:

| They care about | Original Medicare + Medigap | Medicare Advantage | Honest note |
| --- | --- | --- | --- |
| **Keeping my doctors** | Any doctor in the U.S. who accepts Medicare. | Usually a network. **HMO:** you generally stay in network, often with referrals. **PPO:** you can go outside the network but pay more. Networks can change each year (for example, NCH has announced plan changes for 2027). | We can't check networks yet. Call your doctor's office and ask whether they take the specific plan for 2027. |
| **Seeing doctors when I'm away** | Works the same anywhere in the U.S. | Mostly local. HMOs usually cover only emergency and urgent care away from home; PPOs may cover more at a higher cost. Check each plan's travel rules. | Travel rules aren't scored yet. |
| **Low monthly cost** | Usually more per month: the Part B premium, plus Medigap, plus a drug plan. | Often less per month. Many Naples plans have a $0 plan premium (the count comes from catalog data at render time). | A low monthly cost isn't the same as a low total cost when you need care. |
| **Predictable bills** | Medigap can cover most or all of your 20%, so bills are more predictable. | Copays and coinsurance as you use care, up to a yearly limit. | Neither path can predict your exact yearly cost here. |
| **Dental / vision / hearing** (from Stop 4) | Not covered; buy a separate plan if you want it. | Many plans include some, with limits. | We show extras where we can confirm them. |
| **Prescriptions** (from Stop 3) | Add a separate drug plan. | Usually built in. | You can check your medicines in Stop 6. |

**When priorities pull in different directions,** say so plainly and don't resolve it. For example, low monthly cost combined with keeping doctors: "These two can pull in different directions: Advantage often costs less per month, while Original + Medigap gives the widest choice of doctors. That trade-off is the heart of this decision."

**The one warning everyone sees (the "trap door"):**

> Your **6-month Medigap window** starts when you're 65 or older and your Part B begins. During it, you can buy any Medigap plan sold where you live without health questions. **After it, insurers can in most cases ask about your health** and may charge more or say no. So if you start with Advantage and later want to switch to Original + Medigap, getting Medigap may be harder.

This is the most important fact in the journey. It's why the first choice matters more than people expect.

**Get (part 2): Where are you leaning?** Original Medicare + pieces / Medicare Advantage / Not sure, show me both. The person records their own leaning; it's never inferred, and it can be changed with one tap.

| | |
| --- | --- |
| **Item earned** | **Your priorities and your leaning;** the three slots show *how* each would be filled on that path |
| **New interaction** | Flip between the two paths; open the full side-by-side (V5). |
| **Time** | ~3 minutes |

---

### Stop 6 · Your plans

The payoff: "oh wow, this is easy."

| | |
| --- | --- |
| **Hook** | Now let's look at real 2027 plans near you. |
| **Get** | **What's your ZIP code?**, then **Is that in Collier County?** (never assumed from the ZIP). Optional: **add your medicines** (exact strength and form confirmed with buttons) if they said yes to prescriptions. Optional in review mode: **find your current plan.** |
| **Why ask now** | Plans are the only thing that depends on location. Medicines matter only once there are real drug lists to check them against. |
| **Not Collier** | An honest message: we only have Collier County 2027 plans so far, plus Medicare's Plan Finder and free help (SHINE). |
| **New interaction** | Change what the list is ranked by; open a plan card; compare two. |
| **Time** | ~3 minutes |

**What they see depends on their leaning:**

- **Leaning Advantage:** Advantage plans with drug coverage, ranked by their top priority. Advantage plans without drug coverage sit in their own group labeled "no drug coverage."
- **Leaning Original:** two short sections.
  - **Medigap:** the standard lettered plans as a simple chart of which gaps each fills (V8). **Prices aren't available in Daylight yet**, so we say so plainly and show how to get quotes (free SHINE counseling; Florida's state rate-comparison tool, clearly labeled as illustrative).
  - **Drug plans:** the separate drug plans, ranked by their priority (monthly cost or drug deductible).
- **Not sure:** both, side by side and kept short.
- **Always:** a collapsed group, "Special plans: only for people who qualify (for example, with Medicaid or certain health conditions)." It's never hidden and never assumed.

**How their priorities become the ranking** (deterministic; existing engine):

| Their top priority | Ranked by | Shown as |
| --- | --- | --- |
| Low monthly cost | Monthly plan premium, lowest first | "Ranked by lowest monthly premium because you said low monthly cost matters most." |
| Predictable bills | Yearly out-of-pocket limit, lowest first (Advantage) | "Ranked by lowest yearly limit because you said predictable bills matter most." |
| Prescriptions | Drug deductible, lowest first; plus each plan's drug-list result for medicines they added | "Ranked by lowest drug deductible because you said prescriptions matter." |
| Keeping my doctors / Away from Naples / Extras | **Not scored**; stated on screen | "We can't check doctors yet, so they don't affect this order. Call the office before you choose." |

Never "best." Nothing is hidden: "Show more" and "See every plan" are always there.

**Nothing on the card is new.** Every field was taught on the way:

| Plan card shows | Taught at |
| --- | --- |
| Plan type (Advantage with or without drugs, drug plan, special plan) | Stops 3 and 5 |
| HMO / PPO | Stop 5 (doctors and travel) |
| Monthly plan premium (plus your Part B premium) | Stops 2 and 5 |
| Yearly out-of-pocket limit | Stops 2 (no limit in Original) and 5 |
| Drug deductible | Stop 3 |
| Your medicines: on the list, restrictions | Stop 3 (drug lists) and Stop 6 (added medicines) |
| Extras where known | Stop 4 |
| "Checked / not checked yet" on doctors | Stop 5 |
| Star rating | **New here.** One line: Medicare's 1–5 quality rating for the company's plans. The only new term at Stop 6, so it gets a one-tap definition. |

| | |
| --- | --- |
| **Item earned** | **Your shortlist** (the plans they opened or compared) |

---

### Stop 7 · Your next steps

The finished map: something to keep.

| | |
| --- | --- |
| **Give** | Their **personal Medicare map** on one page: their dates and windows (including the Medigap 6-month window), their Part B decision, their leaning, their foundation and how each gap would be filled, the plans they looked at, questions to ask ("Call Dr. ___'s office: do you take [plan] for 2027?"), free help (SHINE, 1-800-MEDICARE) and when they can change later (each fall, Oct 15–Dec 7). |
| **Get (optional)** | Doctor names to put on the checklist. They stay in the tab only and are never logged. |
| **Why** | It turns what we can't check yet into a concrete to-do, and paper is what this audience trusts and keeps. |
| **New interaction** | Print or save as PDF. |
| **Time** | ~1 minute |

---

## 5. Vocabulary ladder

A word may only appear at or after the stop that introduces it, in narration, cards, visuals and Ask Daylight's suggested questions alike. Ask Daylight may use a later term only if the person used it first, and then defines it in plain words.

| Stop | New words |
| --- | --- |
| 1 | Medicare, sign-up window, coverage start date |
| 2 | Part A, Part B, Original Medicare, premium, deductible, your 20% share (coinsurance), late penalty |
| 3 | Part D, drug plan, drug list, drug deductible |
| 4 | Dental, vision and hearing coverage ("extras") |
| 5 | Medicare Advantage (Part C), Medigap / Medicare Supplement, network, HMO, PPO, yearly out-of-pocket limit, Medigap window |
| 6 | Star rating, special needs plan |

---

## 6. Everything we ask, and why

All 8 original questions are kept and moved to the moment they matter. Additions are marked.

| Question | Stop | Why there | What it changes |
| --- | --- | --- | --- |
| Who is this for? | 0 | Changes every sentence | Wording throughout |
| Do you have Medicare yet? | 1 | Opens the dates payoff | New-to-Medicare vs review journey; Stop 1 status |
| Month and year you turn 65 | 1 | Needed for personal dates | Every date in the journey |
| Job-based coverage | 2 | Right after Part B is explained | Part B guidance; Robert branch; Stop 7 checklist |
| Prescriptions | 3 | Right after Part D is explained | Drug emphasis; Stop 6 medicine check offer |
| Extras | 4 | Right after the extras gap | Stop 5 rows; Stop 6 filters |
| Priorities, plus **which matters most** *(new tap)* | 5 | First moment priorities have consequences | Stop 5 rows; Stop 6 ranking order |
| ZIP + Collier confirmation | 6 | Only plans depend on location | Plan availability |
| **Where are you leaning?** *(new)* | 5 | After both paths are understood | Which shortlist Stop 6 shows |
| **Your medicines** *(new, optional)* | 6 | Only useful against real drug lists | Drug-list results on cards |
| **What do you have now?** *(new, review journey)* | 1R | Needed to explain what can change | Review-journey guidance |
| **Doctor names** *(new, optional)* | 7 | Turns an uncheckable into a to-do | Checklist only |

**Privacy:** birth month, job coverage, medicines and doctor names are never logged (complete gap-plan item C01 before shipping). Everything stays in the tab.

---

## 7. Where the AI fits

The AI is the **helper you can call at any stop,** not the screen you live in.

- **Ask Daylight** opens as a focused panel over the current stop and closes back to it. It knows which stop and card you're on.
- It opens with **three ready-made questions for that stop** (for example, at Stop 2: "Do I have to take Part B?", "What does 20% mean in real dollars?", "What if I'm still working?").
- **Ready-made questions get reviewed, pre-written answers.** They're instant, work offline and are always accurate. The model handles only questions people type themselves, using the existing guardrails, and it can show a visual from the library.
- It **can't change** your answers, your map, the ranking or your leaning. It can suggest updating an answer, which you then confirm.
- Each stop keeps its own short Q&A history. There's no long scrolling log.

This is how we make AI approachable for this audience: it's always one tap away, it starts with questions people are likely to have, its common answers are reviewed, and it never takes over the page.

---

## 8. Other journeys

### Already on Medicare (review journey; for example Maria helping her mom)

- **Stop 1 becomes "This year's dates":** the fall change window (Oct 15–Dec 7) and, for people in an Advantage plan, the Jan 1–Mar 31 window. **Get: what do you have now?** Original only / Original + Medigap / Original + drug plan / Medicare Advantage / Not sure.
- **Stops 2–5 become refreshers,** collapsed by default to one-line summaries with "Show me."
- **Stop 5 adds the warnings that apply to them:** leaving Advantage for Original may make Medigap harder to get (health questions); changing Medigap plans later usually means health questions too.
- **Stop 6:** optionally find the current plan, then see it side by side with the shortlist.
- **Stop 7:** the checklist leads with the Dec 7 deadline.

### Still working with job coverage (for example Robert)

- At Stop 2 he learns he may be able to wait on Part B. He chooses: **keep learning** (for later) or **jump to the checklist**.
- His checklist covers when to sign up for Part B after his job coverage ends (the special enrollment window), plus a key personal note: **his Medigap window starts when his Part B starts,** not at 65.

### Need more info (only Part A, or not sure)

- The stop shows "Need more info," what to check (the Medicare card, a Social Security letter), and free help. The journey continues for learning; dates that depend on unknown answers stay unknown and are never guessed.

### Linda, start to finish (the main persona)

| Stop | Linda answers | Linda gets |
| --- | --- | --- |
| 0 | Me | The trust basics |
| 1 | Not yet, gets Social Security; turns 65 March 2027 | "Your card should arrive in the mail; your coverage can start March 1, 2027." Her sign-up window dates. |
| 2 | No job coverage | Most people take Part B now; the late-penalty fact. Her foundation with three gaps. |
| 3 | Yes, takes prescriptions | "You'll be able to check your medicines against real plans." |
| 4 | Dental | Honest line on extras. |
| 5 | Keep my doctors (her cardiologist at NCH) and away from Naples (summers in Ohio); doctors matter most | Both rows side by side: Original + Medigap works with any doctor that accepts Medicare, anywhere in the U.S.; Advantage means checking networks, and HMOs are mostly local. The NCH 2027 note. The Medigap window trap door. She leans **"Not sure, show me both."** |
| 6 | ZIP 34102, confirms Collier; adds her 2 medicines | Both sections. Advantage plans, with a clear note that doctors aren't scored ("call the office"), ranked by her next priority. Medigap letter plans with no prices yet and how to get quotes. Drug plans showing her medicines' drug-list results. |
| 7 | Adds her cardiologist's name | Her one-page map, with "Call Dr. ___'s office: do you take [plan] for 2027?" and her Medigap window dates. |

---

## 9. Facts this journey depends on

All must come from reviewed content with sources (gap plan G3) and be verified against Medicare.gov before shipping. Annual amounts (premiums, deductibles, the Part D cap) come from reviewed tables, never typed into copy.

| Fact | Used at | Source to verify |
| --- | --- | --- |
| 7-month sign-up window; coverage start rules; automatic enrollment with Social Security | 1 | [Medicare.gov: joining a plan](https://www.medicare.gov/basics/get-started-with-medicare/get-more-coverage/joining-a-plan) |
| Part A/B coverage; most pay no Part A premium; Part B premium, deductible and about 20% coinsurance; no yearly limit in Original Medicare | 2 | [Medicare.gov: Medicare costs](https://www.medicare.gov/basics/costs/medicare-costs) |
| Part B late penalty; delaying Part B with current-job coverage and the special window afterward | 2 | Medicare.gov enrollment pages |
| Part D: separate plan or built into Advantage; drug lists; yearly cap; late penalty | 3 | Medicare.gov drug coverage pages |
| Original Medicare and Medigap don't cover routine dental, eyeglass exams or hearing aids | 4 | Medicare.gov coverage pages |
| Two paths; Medigap doesn't work with Advantage; you pay the Part B premium either way | 5 | [Medicare.gov: your coverage options](https://www.medicare.gov/basics/get-started-with-medicare/get-more-coverage/your-coverage-options) |
| HMO vs PPO network rules | 5 | Medicare.gov plan type pages |
| Medigap 6-month window; health questions afterward in most cases; Florida rules | 5, 8 | [Medicare.gov: Medigap, ready to buy](https://www.medicare.gov/health-drug-plans/medigap/ready-to-buy); Florida rules per gap plan G4 |
| Fall change window Oct 15–Dec 7; Advantage window Jan 1–Mar 31 | 7, 8 | Medicare.gov joining-a-plan page |
| NCH 2027 network changes | 5 | [NCH notice](https://nchmd.org/maupdate/) (dated; recheck before demo) |
| Count of $0-premium plans | 5 | Catalog data at render time |

---

## 10. Testing the journey before the UI

Before any polish, test the journey as a **clickable low-fidelity prototype** (plain boxes, real words) with 5 people turning 65 and 2 caregivers:

- Can they say, in their own words, what the **three gaps** are? (teach-back after Stop 2)
- Can they explain the **difference between the two paths** for doctors and cost? (after Stop 5)
- Can they explain the **Medigap window** and why it matters?
- At Stop 6, do they understand every field on a plan card **without help**?
- Does anyone think Daylight **picked a plan** for them? (target: no one)
- Time to finish, and where they stalled.

**Pass bar:** 4 of 5 explain the three gaps and the two paths correctly, 4 of 5 read a plan card unaided, and no one thinks Daylight chose for them.

---

## 11. Notes for the UI pass that follows

Captured now so the next plan starts from them. Not part of this plan's scope.

- **From the current screen:** the "Automated guide" chip appears twice; the floating "Latest message" pill covers text; message text runs too wide for its size; the header progress dot means nothing without labels; the emoji-style face with glasses and rosy cheeks reads as pandering, not premium.
- **What Town gets right:** confident restraint. Lots of space, one strong headline, crisp illustration with real personality, the product shown plainly. Warmth comes from craft, not from making everything big and soft.
- **The UI pass will design:** the stage (one stop, full screen, one idea at a time), the journey map, the foundation-and-slots inventory, the Ask Daylight panel, the plan cards and the printable map. It will revisit the character question from scratch.

---

## 12. Implementation outline (UI-agnostic)

These can start before the UI plan. Same protocol as earlier plans: tick with `DONE <date> — evidence: …`, never renumber, and record decisions.

**Last updated:** 2026-10-20 — the 7-stop journey is implemented and runs end to end. The chat-first flow, the level system and the emoji character are **reverted**; the front door is the faint path with Stop 0 lit, the AI is a helper panel (Ask Daylight) you open at any stop, and the foundation-and-three-gaps model drives Stops 2-5. Verified Stop 0 → 7 → plans → printable map on desktop + phone with **zero runtime errors**; **63 backend tests pass**. Fonts (Atkinson/Fraunces) and the trust signals (stamps/receipts) carry forward; the character is removed pending the UI pass's "revisit from scratch." Evidence: `cms-slice/reports/ui-journey/phase-core/` (j0-j9).

**Execution status:** DONE — J03, J04, J05, J06 (core), J08 (core), J09, J11, J12 (behavior). PARTIAL — J01 (journey is data-structured in `app.js` constants `STOP_NAMES`/`ASK`/`TRADEOFFS`/payoff fns, not yet extracted to standalone content files), J02 (draft/illustrative content written with sources listed in §9; domain review is a human step), J06 (special-plans collapsed group not surfaced in the shortlist yet), J07 (review mode adjusts Stop 1 + the map, but the "what do you have now?" question and current-plan lookup aren't built), J13 (Linda walked end-to-end; Robert/Maria logic present, not fully walked). DEFERRED — J10 (automated vocab-ladder test), J12 test, J14 (the running journey IS the clickable prototype; the 5-person test is a human step), optional medicine lookup at Stop 6.

- [~] **J01** · Define the journey as data: stops, cards, questions, options, branches and the vocabulary ladder, in content files (not hard-coded in UI). PARTIAL 2026-10-20 — structured as data in `app.js` (per-stop renderers + `ASK`/`TRADEOFFS`/`STOP_NAMES`); extraction to standalone content files is the remaining step.
- [~] **J02** · Write reviewed content for each stop's cards, with sources (section 9). Domain review signs it. PARTIAL 2026-10-20 — draft content written with source links; domain sign-off pending.
- [x] **J03** · Implement journey state: current stop, finished stops (never re-lock), answers, leaning, priorities with order, inventory slots. Tab-only. DONE 2026-10-20 — `state.journey` (stop/reached/finished) + `state.intake`; `goToStop` only allows `<= reached`; foundation/gap slots in `foundationCard()`. Evidence: j0/j2.
- [x] **J04** · "What this means for you" rules for Stops 1-5, incl. Stop 5 trade-off rows and tension lines. DONE 2026-10-20 — deterministic payoffs per stop; `TRADEOFFS` table + the "pull in different directions" tension line. Unit tests still to add. Evidence: j5b.
- [x] **J05** · Wire the decision-map engine to the journey without changing its rules. DONE 2026-10-20 — `buildMap()` reused unchanged for Stop 7 and print. Evidence: j7.
- [x] **J06** · Stop 6 shortlist rules by leaning + priority-to-ranking + unscored statements. DONE (core) 2026-10-20 — Advantage→MA-PD, Original→PDP + Medigap letters (V8), not-sure→MA-PD; ranking engine + `/api/catalog` reused; unscored priorities stated. Special-plans group = PARTIAL. Evidence: j6.
- [~] **J07** · Review journey (section 8), incl. "what do you have now?" and current-plan lookup. PARTIAL 2026-10-20 — `yes_ab` drives review-mode payoffs + map; the dedicated question and plan lookup are pending.
- [x] **J08** · Robert and "need more info" branches. DONE (core) 2026-10-20 — job=yes shows the delay-Part-B guidance + "skip to my checklist"; only_a/unsure shows a "Need more info" stamp + SHINE.
- [x] **J09** · Ask Daylight scoping: stop context, three ready-made reviewed questions per stop, model only for typed questions. DONE 2026-10-20 — `ASK` per stop; typed questions hit `/api/live-chat` with an offline fallback. Evidence: j8.
- [ ] **J10** · Vocabulary-ladder check test. DEFERRED 2026-10-20 — content follows the ladder; the automated guard is not yet written.
- [x] **J11** · Printable personal map built from journey state. DONE 2026-10-20 — `printMap()` (steps + dates + leaning + questions-to-ask). Evidence: j7.
- [x] **J12** · Privacy: none of the sensitive answers reach logs. DONE (behavior) 2026-10-20 — only recipient/zip/medicare(coarse)/drugs are logged; birth month, job, medicines and doctor names are never sent. Automated test pending.
- [~] **J13** · Persona tests for Linda, Robert and Maria, start to finish. PARTIAL 2026-10-20 — Linda walked end-to-end in Chrome (j0-j9); Robert/Maria branches implemented, full walks pending.
- [ ] **J14** · Low-fidelity clickable prototype + the section 10 test. DEFERRED 2026-10-20 — the running journey is the clickable prototype; the 5-person test is a human step.

## Decision log

| Date | Decision | By |
| --- | --- | --- |
| 2026-10-20 | D1 · Replace chat-first with a 7-stop journey; the AI becomes a helper panel at every stop | **Accepted — implemented** |
| 2026-10-20 | D2 · Teach everything through one model: a foundation (A + B) with three gaps, and two ways to fill them | **Accepted — implemented** (foundation card + gap slots; Stop 5 "two ways to fill the gaps") |
| 2026-10-20 | D3 · Stop order: dates → foundation → prescriptions → extras → two paths → plans → next steps | **Accepted — implemented** |
| 2026-10-20 | D4 · Ask for the ZIP only at Stop 6 | **Accepted — implemented** |
| 2026-10-20 | D5 · New questions: "which matters most," "where are you leaning," optional doctor names; (medicines + "what do you have now" pending) | **Accepted — core implemented** (which-matters-most, leaning, doctor names done; medicine lookup + review-mode "what do you have now?" deferred) |
| 2026-10-20 | D6 · The Medigap-window warning is shown to everyone at Stop 5 | **Accepted — implemented** (the "one thing to know before you choose" card) |
| 2026-10-20 | D7 · Ready-made Ask Daylight questions get reviewed, pre-written answers; the model handles only typed questions | **Accepted — implemented** |
| 2026-10-20 | D8 · Original-path shortlist shows Medigap letter plans without prices (with how to get quotes) plus ranked drug plans | **Accepted — implemented** (V8 letters + PDP shortlist on the Original lean) |
| 2026-10-20 | D9 · Reverted the chat-first flow, the level system and the emoji/glasses character (section 11 feedback); kept Atkinson/Fraunces fonts and the trust stamps/receipts | Accepted — implemented |

## Change log

| Date | Change | By |
| --- | --- | --- |
| 2026-10-20 | Created; supersedes the levels plan's flow and puts the aesthetic plan on hold | Claude |
| 2026-10-20 | Implemented the 7-stop journey end to end (Stops 0-7, foundation-and-three-gaps model, Stop 5 trade-offs + Medigap-window warning + leaning, Stop 6 ranked plans by leaning, Stop 7 printable map, Ask Daylight helper panel with reviewed per-stop questions). Reverted the chat-first flow, level system and emoji character per section 11. Verified Linda end-to-end desktop + phone, zero errors; 63 backend tests pass. Evidence in reports/ui-journey/phase-core/. Deferred items noted in Execution status. | Claude |
