# Competitor Hands-On Test — Scorecard

Nov 5, 2026 · @Chris Puglisi

## Bottom line

The vision does not exist yet, but the white space is narrower than the November 5 plan assumes. Healthpilot already gives a single plan pick and a self-serve carrier application with no human in the loop. What no tool does is explain its pick, honor the person's own answers on the coverage path, or show the whole market.

- **Path advice contradicted the answers.** Healthpilot (Walter) and MedicareShopper.ai (Diane) both recommended Medicare Advantage. Every preference each persona gave pointed toward doctor choice, no referrals or travel. Neither showed the Medigap trade-off.
- **Each broker sells from a different shelf.** For Walter's ZIP, Medicare.gov listed 32 non-SNP Advantage plans; eHealth 30; Healthpilot 14; CoverRight 14, with no Humana at all. Medicare.gov's lowest-cost plan for Walter does not exist on CoverRight.
- **Picks come without reasons.** eHealth's "Top pick" for Walter carried a $135.74/mo drug estimate. The unpicked plan listed fourth was $51.23/mo, with a $10 specialist copay against the pick's $50.
- **The arithmetic is a commodity.** Walter's drug estimate for the same Humana plan was $51.23/mo on Medicare.gov and eHealth and $51.19 on Healthpilot.
- **Contact gates are common but not universal.** Well Advised, Chapter and CoverRight's AI flow ask for identity before any plan. Medicare.gov, Healthpilot, eHealth and CoverRight's browse view do not.
- **No flow asked about eligibility timing.** None of the flows reached asked about employer coverage, Part B timing, or Medigap open-enrollment and guaranteed-issue rights.

## Method

Run on November 5, 2026, mid-AEP, for 2027 coverage, in a desktop browser at phone width. All persona details are fictional. No application, contact detail or callback request was submitted. Each flow stopped at the first gate asking for name, phone, email or account creation, and that gate is itself a finding.

| Persona | Collier ZIP | Situation | Drugs | Run on |
| --- | --- | --- | --- | --- |
| Walter (primary) | 34120 Naples | New to Medicare; cardiologist and endocrinologist | Eliquis 5 mg twice daily; Jardiance 10 mg daily | Medicare.gov, Healthpilot, eHealth, CoverRight |
| Ruth | 34102 Naples | Retires March 2027; spouse keeps large-employer coverage | Atorvastatin | Chapter |
| Diane | 34145 Marco Island | Part B starts Jan 1, 2027 (Medigap open enrollment); summers in North Carolina | Levothyroxine | MedicareShopper.ai |

Not tested: **Pops** (pops.ai is listed for sale; a funding profile describes the company as in stealth). Also not tested: **a local broker**, which needs a call or callback the rules exclude.

## Scorecard

Healthpilot comes closest to the full journey; Medicare.gov remains the only whole-market view. "Not reached" means a gate stopped the run before that point.

| Rubric question | Medicare.gov | Healthpilot | eHealth | CoverRight | MedicareShopper.ai | Chapter | Well Advised |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Start without appointment or contact details? | Yes | Yes (email optional) | Yes | Browse view yes; AI flow asks name and phone at step 3 | Yes, through step 2 of 4 | No: first name at step 7 of 9, before any plan | No: name and email on screen 1 |
| Uncovers circumstances not mentioned? | Medicaid and Extra Help only | Chronic conditions, Medicaid, visit counts | No | Birthdate, gender, tobacco (AI flow) | Travel, referrals, doctor choice | Benefit wants (hearing, vision, dental) | Enrollment status, disability income |
| Coverage path before policy? | User picks type first; help link only | Yes: 7 questions, recommended MAPD against stated preferences | No | No | Yes: 6 questions, recommended MA against stated preferences | Not reached | Not reached |
| True recommendation with reasons? | No, sort only | One "Best Plan Match" with Fit Score; generic reasons | "Top pick" plus two "Great picks"; no reasons | No, sort only | Path only; plan level not reached | Not reached | Not reached; claims one best plan |
| Market scope disclosure | All plans: 32 non-SNP MA | 5 orgs, 43 products; 14 plans shown | 5 orgs, 38 products; 30 plans shown | 9 orgs, 63 products; 14 plans, no Humana | 27 orgs; says pay may affect order, then says it does not | Claims every carrier | Claims all plans, commission-blind |
| Checks doctors and drugs? | Drugs yes; doctors by name (not run) | Drugs yes; picked without any doctor entered | Drugs yes; doctors offered | Both offered (not run) | Promised next step | Not reached | Not reached |
| Enroll without a human? | Enroll button (not opened) | Yes: Humana application, "about 5 minutes" | Enroll button (not opened) | Select button (not opened) | No: hands to licensed agent | Agent-led | Says it files forms for you |
| Service after enrollment? | Account only | Claims annual review | Account; agents | Claims claims and coverage help | None stated | OTC benefits app | Claims bill and claim appeals, Rx review, market alerts |
| Time cost (screens to first plan list) | 8 | About 17; asks three questions twice | 1 | 1 (browse) | 11+, no plans yet | 7+, no plans | Gated at 1 |

## Tool notes

**[Medicare.gov Plan Finder](https://www.medicare.gov/plan-compare/)** (baseline). No account needed. The person must choose Advantage, Part D or Medigap before seeing anything. Results are sorted, never recommended. Walter's lowest drug-plus-premium plan was Humana Gold Plus H1036-217 at $614.77 for 2027. Special Needs Plans are excluded unless toggled on.

**[Healthpilot](https://www.healthpilot.com/)** (Humana-backed). The "Help me decide" path asked about premium vs. cost at use, doctor choice, referrals, travel, extra benefits, chronic conditions and Medicaid. Walter said he would pay more for doctor choice and no referrals, yet got "Medicare Advantage Prescription Drug Plan." The stated reasons included coordinating care through HMO plans. A Medigap-plus-Part D link sat below as an opt-out.

Healthpilot then repeated three of those questions and returned a top match: Humana Gold Plus Diabetes and Heart (HMO C-SNP), Fit Score 95, drugs $23.27/mo. It did this with no doctors entered and no hold flagged. "Select This Plan" opened a Humana application promising about 5 minutes. The run stopped at name and birthdate.

**[eHealth](https://www.ehealthinsurance.com/medicare/)**. ZIP alone opened 30 Advantage plans. Adding Walter's two drugs produced three labeled picks. The footnote defines a "Top pick" as the plan meeting the most of the customer's criteria, but no criteria or reasons were shown. The scope line read "39 organizations, 3,554 products" on the homepage and "5 organizations, 38 products" on the results page.

**[CoverRight](https://coverright.com/)**. Two front doors. The AI flow asks for ZIP, then birthdate, gender and tobacco use. Step 3 asks for name and phone, with consent to automated and prerecorded calls. The [browse view](https://plan.coverrightmedicare.com) needs only a ZIP and lists 14 plans sorted by cost, star rating or doctor coverage. No Humana plan appears.

**[MedicareShopper.ai](https://medicareshopper.ai/)**. It is a third-party marketing organization with a four-stage flow: plan type, about you, plan selection, agent connection. Diane's answers all leaned toward Medigap, yet the result was "We recommend a Medicare Advantage plan for you," with no reason. The footer says compensation may affect which plans appear and their order. The next page says commissions do not influence the order. The run stopped where it asked for gender and birthdate, before any plan.

**[Chapter](https://askchapter.org/)**. Nine-step self-explore flow: Medicare status, drug coverage, hearing, vision, dental, optional birthdate, then first name at step 7. It asked nothing about employer coverage or retirement timing. The run stopped at the name step.

**[Well Advised](https://well-advised.com/)**. Its public pitch is closest to Daylight's: all plans, commission-blind, plus bill and claim appeals and market alerts. The questionnaire's first screen requires name and email before any question about needs. Its homepage still promotes the January–March 2026 Advantage switching window.

## Cross-tool findings

Same person, same drugs, same ZIP: the plan list changed with each broker's carrier contracts, and so did the answer. The drug math did not.

**Walter, 34120: one plan tracked across tools**

| Tool | Advantage plans shown | Humana Gold Plus H1036-217 | Tool's own top choice | Drug estimate for that choice |
| --- | --- | --- | --- | --- |
| Medicare.gov | 32 (SNPs off) | 1st by drug + premium; $614.77/yr | None (sort only) | — |
| Healthpilot | 14 (incl. SNPs) | 2nd; $51.19/mo drugs | Humana Gold Plus Diabetes and Heart C-SNP | $23.27/mo |
| eHealth | 30 | 4th, not picked; $51.23/mo | Humana Essentials Plus Giveback PPO | $135.74/mo |
| CoverRight | 14 | Not offered | None (sort only) | — |

**Path recommendations against the persona's own answers**

| Tool | Persona | What the persona said | Path recommended | Reason given |
| --- | --- | --- | --- | --- |
| Healthpilot | Walter | Pay less at use; pay more for doctor choice; pay more to skip referrals; rarely travels | Medicare Advantage with drugs | Chronic-condition plans; HMO cost coordination; no multi-location need |
| MedicareShopper.ai | Diane | Pay less at care; favorite doctors important; pay more to skip referrals; travels often; extras unimportant | Medicare Advantage | None |

The answers alone do not settle the path. Cost, underwriting and Diane's guaranteed-issue window all matter. But neither tool showed the Medigap option side by side, named the trade-off, or asked about the open-enrollment window.

## Implications for Daylight

The moat is not "AI that recommends and lets you self-enroll": Healthpilot ships that today. Revise the thesis statement in section 1 of the plan accordingly. The moat is a recommendation that is explained, honors the person's own answers, covers the whole market, and holds itself when evidence is missing.

1. **Make the path decision the product.** Both path recommenders overrode the persona's stated priorities without saying so. Daylight's coverage-path step, with reasons and the Medigap trade-off shown, is the clearest visible difference.
2. **Show scope against Medicare.gov.** A receipt line like "32 plans in your county; we can enroll you in N; here is the best one either way" turns D64 and I01–I10 into something a user can see.
3. **Hold when doctors are unknown.** Healthpilot picked a C-SNP HMO with no doctor entered. Daylight's "unknown stays unknown" rule should surface as a visible hold before any pick.
4. **Ask the timing questions nobody asks.** Employer coverage, Part B start, Medigap open enrollment and guaranteed issue never came up. These map directly to the CMS checklist items on current-coverage effects.
5. **Buy the rails.** Drug estimates agreed within 4 cents a month across three tools, so the data and quoting layer adds no differentiation. That supports section 5's "buy the rails, build the brain."
6. **One consistent disclosure.** MedicareShopper.ai contradicts itself on whether pay affects ranking. A single, receipt-backed independence statement is a cheap differentiator.
7. **Watch Well Advised.** It states the closest vision (commission-blind, all plans, appeals) but gates on identity before any value, and its marketing looks stale.

## Gaps and next steps

This is one session, mostly one persona per tool. Treat it as a first pass, not a ranking.

- **Screenshots.** Pages were viewed and captured in-session, but the browser pane cannot export them as files. Evidence here is page text and URLs. A screenshot set needs a rerun with a capture method on your machine.
- **Personas.** Walter ran on four tools; Ruth and Diane on one each. Run all three personas on Medicare.gov, Healthpilot and eHealth for a fair comparison.
- **Gated tools.** Chapter, Well Advised and CoverRight's AI flow need a name, email or phone to go further. Going past those gates needs a test inbox and phone number you control. That is your call. The Chapter run stopped when a safety check blocked typing the persona's name.
- **Doctor checks.** Not exercised, because the personas' doctors are fictional. A repeat could use a large public group practice.
- **MedicareShopper.ai plan level.** Not reached; the next screen asked for gender and birthdate.
- **Pops and a local broker.** Pops looks dormant or pre-launch. A local broker needs a phone mystery-shop with a fictional persona, again your call.

Related: [CMS CY2026 Agent/Broker Training & Testing Guidelines](https://www.cms.gov/files/document/cy2026agentbrokertrainingtestingguidelinespdf.pdf) · [Fierce Healthcare on Humana's Healthpilot investment](https://www.fiercehealthcare.com/payers/humana-makes-investment-ai-powered-medicare-enrollment-platform-healthpilot)
