# Readiness trigger matrix

Research draft · October 22, 2026 · **Not implemented or professionally validated.** Thirty stable trigger IDs are a rule inventory, not thirty required questions. Baseline means necessary for a requested capability, not mandatory for education/browsing. Every primary question has one short why line; detailed rationale stays here or in optional help. See [main contract](READINESS_DESIGN.md) and [source notes](READINESS_SOURCES.md).

## Index

| ID | Topic | Class | Scope |
|---|---|---|---|
| [RC01](#rc01) | One person and requested check | baseline_by_capability | MVP |
| [RC02](#rc02) | Residence/service area | baseline_by_capability | MVP |
| [RC03](#rc03) | Benefit year and intended start | baseline_by_capability | MVP |
| [RC04](#rc04) | Actual A/B enrollment | baseline_by_capability | MVP |
| [RC05](#rc05) | Actual effective dates | baseline_by_capability | MVP |
| [RC06](#rc06) | Age/eligibility basis | conditional | MVP |
| [RC07](#rc07) | Current arrangement vs planned change | conditional | MVP |
| [RC08](#rc08) | Enrollment event/window | conditional | MVP |
| [RC09](#rc09) | Current employment vs continuation | conditional | MVP |
| [RC10](#rc10) | Relevant employer size | conditional | MVP |
| [RC11](#rc11) | Separate loss/job dates | conditional | MVP |
| [RC12](#rc12) | Creditable drug coverage/gap | conditional | MVP |
| [RC13](#rc13) | Retiree/family benefit consequences | conditional | MVP |
| [RC14](#rc14) | HSA timing | conditional | MVP |
| [RC15](#rc15) | Florida Medigap purchase window | conditional | MVP |
| [RC16](#rc16) | Trial/guaranteed-issue history | conditional | MVP |
| [RC17](#rc17) | Existing Medigap replacement | conditional | MVP |
| [RC18](#rc18) | Assistance status without financial intake | conditional | MVP |
| [RC19](#rc19) | SNP-specific qualification | conditional | MVP flags/referral; detailed SNP matching future |
| [RC20](#rc20) | Seasonal/routine travel | conditional | MVP |
| [RC21](#rc21) | Exact provider identity/location | conditional | MVP |
| [RC22](#rc22) | Exact prescription identity | conditional | MVP |
| [RC23](#rc23) | Supply and pharmacy | conditional | MVP |
| [RC24](#rc24) | Restrictions and Part B/D boundary | conditional | MVP |
| [RC25](#rc25) | Affordability vs preference | conditional | MVP |
| [RC26](#rc26) | Military/veterans coordination | conditional | MVP |
| [RC27](#rc27) | Material exception/continuity | conditional | MVP recognition/referral; rare-case automation future |
| [RC28](#rc28) | Conflicting or ambiguous proposed facts | integrity_guard | MVP |
| [RC29](#rc29) | Source/data capability guard | system_no_question | MVP |
| [RC30](#rc30) | Final plan-specific review | post_selection_not_queue | Future; separate final gate |

<a id="rc01"></a>
## RC01 · One person and requested check

**Trigger / scope:** A personal comparison is requested and recipient or requested capability is unconfirmed. Reuse a confirmed Ask fact; education-only may bypass. **baseline_by_capability · MVP.**

**Question:** Who is this coverage for?

**Why we ask: We need to keep one person’s details together.**

**Controls:** Me; Someone I help; Research only; Not sure; Something else + text. Every question also supports Not sure, Check later/Defer, Back and Ask. Something else retains brief text and requires confirmed extraction; no invented enum. RC29/RC30 are boundary controls, not automatically queued questions.

**Proposed schema:** `{"subject.role": "self|helper|research|unknown", "request.capabilities": "explicit set"}`. These are design fields, not fields currently accepted by the guest backend.

**Dependencies:** None; integrity guards run before dependent checks.

**Resolution:** Person/context and requested check acknowledged; research may end without personal intake.

**Ambiguity/contradiction:** Caregiver describing own drugs mixed with parent’s coverage: separate profiles, never merge people. Do not demand legal authority just to browse.

**Evidence:** User confirmation for research; formal permission required only before protected-account access/application. User-confirmed remains reported, never independently verified.

**Matching consequence:** Unknown subject holds personalized fit; education/samples remain available.

**Human-help reason:** Helper cannot obtain consent or wants official account access: explain authorization and offer SHINE/Medicare.

**Official support (retrieved October 22, 2026):** [S26: Caregiver permission](https://www.medicare.gov/basics/get-started-with-medicare/using-medicare/5-tips-for-using-medicare) — Tip 2: permission to talk to someone trusted (federal); [S27: Florida SHINE](https://www.floridashine.org/) — Who We Are (Florida). These sources support why the fact matters; scheduling/deduplication and privacy choices are Daylight product policy, not statutory requirements.


<a id="rc02"></a>
## RC02 · Residence/service area

**Trigger / scope:** Requested availability/network check lacks usable home ZIP/county, spans counties, or moving/seasonal facts conflict with home. **baseline_by_capability · MVP.**

**Question:** Where is your permanent home?

**Why we ask: Plan availability depends on where you live.**

**Controls:** ZIP + county confirmation; Moving: destination and month; Not sure. Every question also supports Not sure, Check later/Defer, Back and Ask. Something else retains brief text and requires confirmed extraction; no invented enum. RC29/RC30 are boundary controls, not automatically queued questions.

**Proposed schema:** `{"scope.homeZip": "5 digits|unknown", "scope.homeCountyFips": "string|unknown", "scope.residence": "permanent|moving|seasonal|unknown"}`. These are design fields, not fields currently accepted by the guest backend.

**Dependencies:** RC01.

**Resolution:** Usable confirmed home scope, or explicit unknown/out-of-area disposition. Do not re-ask an unambiguous confirmed home report solely because it came from Q3.

**Ambiguity/contradiction:** Mailing address, winter address and provider location are not automatically permanent residence. Multi-county ZIP needs county confirmation.

**Evidence:** Reported home + accepted ZIP/county lookup; actual plan service-area file for plan/year. User-confirmed remains reported, never independently verified.

**Matching consequence:** Unknown/outside Collier holds local personalized availability; no false unavailable-plan conclusion.

**Human-help reason:** Unsettled residence or interstate move: SHINE/plan service-area review.

**Official support (retrieved October 22, 2026):** [S01: Joining a plan](https://www.medicare.gov/basics/get-started-with-medicare/get-more-coverage/joining-a-plan) — Am I eligible?; Initial Enrollment Period; Other enrollment periods (federal); [S17: Special Enrollment Periods](https://www.medicare.gov/basics/get-started-with-medicare/get-more-coverage/joining-a-plan/special-enrollment-periods) — Change where you live; lose coverage; Medicaid/Extra Help; special situations (federal). These sources support why the fact matters; scheduling/deduplication and privacy choices are Daylight product policy, not statutory requirements.


<a id="rc03"></a>
## RC03 · Benefit year and intended start

**Trigger / scope:** Requested benefit year/start is unknown, mismatches source year, or already-on-Medicare answer supplied no comparison year. **baseline_by_capability · MVP.**

**Question:** Which year should we compare?

**Why we ask: Plan benefits and prices can change each year.**

**Controls:** 2026; 2027; Another year + year; Not sure. Every question also supports Not sure, Check later/Defer, Back and Ask. Something else retains brief text and requires confirmed extraction; no invented enum. RC29/RC30 are boundary controls, not automatically queued questions.

**Proposed schema:** `{"scope.benefitYear": "YYYY|unknown", "timing.requestedStart": "YYYY-MM|unknown"}`. These are design fields, not fields currently accepted by the guest backend.

**Dependencies:** RC01.

**Resolution:** Explicit year, reusing confirmed Q4 requested month/year where it determines the requested comparison.

**Ambiguity/contradiction:** Today’s year, future plan year and current enrollment year are distinct. Unsupported year is not an answer error.

**Evidence:** Accepted source manifest for exactly that year; source-date and effective-year metadata. User-confirmed remains reported, never independently verified.

**Matching consequence:** Mismatched/unsupported year holds current cost/availability claims, not general education.

**Human-help reason:** Urgent effective-date uncertainty: Medicare/SHINE.

**Official support (retrieved October 22, 2026):** [S01: Joining a plan](https://www.medicare.gov/basics/get-started-with-medicare/get-more-coverage/joining-a-plan) — Am I eligible?; Initial Enrollment Period; Other enrollment periods (federal); [S24: Medicare costs](https://www.medicare.gov/basics/costs/medicare-costs) — Costs for Parts A/B/C/D and Medigap; year-specific tables (federal/plan). These sources support why the fact matters; scheduling/deduplication and privacy choices are Daylight product policy, not statutory requirements.


<a id="rc04"></a>
## RC04 · Actual A/B enrollment

**Trigger / scope:** Personal health/drug candidates requested and active/pending Part A/Part B status is not independently represented; Q4 Already on Medicare is insufficient. **baseline_by_capability · MVP.**

**Question:** Which Medicare parts do you have now?

**Why we ask: Different plans require different Medicare parts.**

**Controls:** A and B; A only; B only; Neither; Applied; waiting; Not sure. Every question also supports Not sure, Check later/Defer, Back and Ask. Something else retains brief text and requires confirmed extraction; no invented enum. RC29/RC30 are boundary controls, not automatically queued questions.

**Proposed schema:** `{"enrollment.partA.status": "active|pending|not_active|unknown", "enrollment.partB.status": "active|pending|not_active|unknown"}`. These are design fields, not fields currently accepted by the guest backend.

**Dependencies:** RC01.

**Resolution:** Both parts have explicit reported/unknown statuses; pending stays pending.

**Ambiguity/contradiction:** An Advantage member still has A/B. Do not call A+B plus Advantage contradictory. Do not infer premium-free A or eligibility from age.

**Evidence:** Reported status is enough for conditional research; official SSA/Medicare record for verified enrollment. Never collect Medicare number/card image here. User-confirmed remains reported, never independently verified.

**Matching consequence:** Unknown A/B holds eligible-to-join claims; MA requires both, standalone D A or B. Browse only with explicit assumptions.

**Human-help reason:** Not enrolled/uncertain: official SSA/Medicare enrollment help.

**Official support (retrieved October 22, 2026):** [S01: Joining a plan](https://www.medicare.gov/basics/get-started-with-medicare/get-more-coverage/joining-a-plan) — Am I eligible?; Initial Enrollment Period; Other enrollment periods (federal); [S02: Plan for Medicare](https://www.ssa.gov/medicare) — Plan for Medicare; When to sign up (federal). These sources support why the fact matters; scheduling/deduplication and privacy choices are Daylight product policy, not statutory requirements.


<a id="rc05"></a>
## RC05 · Actual effective dates

**Trigger / scope:** Timing/Medigap/change review needs actual A/B dates and they are missing or different from requested start. **baseline_by_capability · MVP.**

**Question:** When did Part B start?

**Why we ask: This can affect your enrollment and Medigap options.**

**Controls:** Month/year selector; Not started yet; Not sure. Every question also supports Not sure, Check later/Defer, Back and Ask. Something else retains brief text and requires confirmed extraction; no invented enum. RC29/RC30 are boundary controls, not automatically queued questions.

**Proposed schema:** `{"enrollment.partB.effective": "date with precision|pending|unknown", "enrollment.partA.effective": "same, asked separately only if needed"}`. These are design fields, not fields currently accepted by the guest backend.

**Dependencies:** RC04.

**Resolution:** Relevant dates recorded with precision and provenance, or timing explicitly held.

**Ambiguity/contradiction:** One date does not establish both parts. Retroactive A differs from B; requested start is never substituted.

**Evidence:** Self-report/card dates without identifier for research; official record for confirmed timing. User-confirmed remains reported, never independently verified.

**Matching consequence:** Missing dates hold affected timing/GI calculations, not already sourced benefit browsing.

**Human-help reason:** Unexpected/retroactive dates: SSA/SHINE.

**Official support (retrieved October 22, 2026):** [S03: When coverage starts](https://www.medicare.gov/basics/get-started-with-medicare/sign-up/when-does-medicare-coverage-start) — Initial Enrollment Period; Signing up for premium-free Part A later; Special Enrollment Period (federal); [S10: Medigap basics](https://www.medicare.gov/health-drug-plans/medigap/basics) — Get Medigap Basics; Open Enrollment (federal). These sources support why the fact matters; scheduling/deduplication and privacy choices are Daylight product policy, not statutory requirements.


<a id="rc06"></a>
## RC06 · Age/eligibility basis

**Trigger / scope:** Timing, premium eligibility or Medigap rights need age/basis that existing confirmed enrollment does not resolve; not a universal diagnosis screen. **conditional · MVP.**

**Question:** How did you first qualify for Medicare?

**Why we ask: Some enrollment rules depend on how you qualified.**

**Controls:** Turning 65; Disability before 65; Kidney failure / ESRD; ALS; Another reason; Not sure. Every question also supports Not sure, Check later/Defer, Back and Ask. Something else retains brief text and requires confirmed extraction; no invented enum. RC29/RC30 are boundary controls, not automatically queued questions.

**Proposed schema:** `{"eligibility.basis": "age|disability|ESRD|ALS|other|unknown", "eligibility.ageBand": "under65|65plus|unknown", "eligibility.birthMonthYear": "optional only when timing needs it", "eligibility.firstDayBirthday": "yes|no|unknown when timing material"}`. These are design fields, not fields currently accepted by the guest backend.

**Dependencies:** RC04.

**Resolution:** Relevant basis/age or explicit unknown; ask birthday month/year only if calculation requires it.

**Ambiguity/contradiction:** Disability benefits are not always active Medicare. ESRD/ALS timing differs. No full birth date or citizenship documents for ordinary research.

**Evidence:** SSA/Medicare determination for verified eligibility; report alone is provisional. User-confirmed remains reported, never independently verified.

**Matching consequence:** Unknown holds basis-dependent timing/rights/quotes; no automatic ineligibility or age-based recommendation.

**Human-help reason:** Non-age/complex eligibility or citizenship/residency eligibility question: SSA/qualified human, without immigration-detail intake.

**Official support (retrieved October 22, 2026):** [S02: Plan for Medicare](https://www.ssa.gov/medicare) — Plan for Medicare; When to sign up (federal); [S03: When coverage starts](https://www.medicare.gov/basics/get-started-with-medicare/sign-up/when-does-medicare-coverage-start) — Initial Enrollment Period; Signing up for premium-free Part A later; Special Enrollment Period (federal); [S28: ESRD](https://www.medicare.gov/basics/end-stage-renal-disease) — Group coverage and coordination period (federal). These sources support why the fact matters; scheduling/deduplication and privacy choices are Daylight product policy, not statutory requirements.


<a id="rc07"></a>
## RC07 · Current arrangement vs planned change

**Trigger / scope:** Current medical arrangement has incompatible same-period reports or user wants to leave MA/Medigap without a clear current-versus-future distinction. **conditional · MVP.**

**Question:** How do you get your A and B benefits now?

**Why we ask: We need to separate current coverage from a possible change.**

**Controls:** Original Medicare; Medicare Advantage; A change is pending; Not sure. Every question also supports Not sure, Check later/Defer, Back and Ask. Something else retains brief text and requires confirmed extraction; no invented enum. RC29/RC30 are boundary controls, not automatically queued questions.

**Proposed schema:** `{"coverage.currentArrangement": "original|advantage|pending_change|unknown", "coverage.planEffective": "dated report|unknown", "coverage.changeIntent": "keep|explore|change|unknown"}`. These are design fields, not fields currently accepted by the guest backend.

**Dependencies:** RC04.

**Resolution:** Current arrangement and any future change separated; contradictory reports preserved with a resolution link.

**Ambiguity/contradiction:** Both Medicare card and MA card can be normal. A reported Medigap policy with MA may be unused/suspended; do not accuse or silently delete it.

**Evidence:** Plan name/ID from safe manual entry if needed, effective date/notice; no membership number. User-confirmed remains reported, never independently verified.

**Matching consequence:** Unresolved arrangement holds safe change-path conclusions and duplicate-coverage assumptions.

**Human-help reason:** Overlapping/pending coverage or cancellation risk: SHINE/plan/benefits administrator.

**Official support (retrieved October 22, 2026):** [S01: Joining a plan](https://www.medicare.gov/basics/get-started-with-medicare/get-more-coverage/joining-a-plan) — Am I eligible?; Initial Enrollment Period; Other enrollment periods (federal); [S09: When can I buy Medigap?](https://www.medicare.gov/health-drug-plans/medigap/ready-to-buy/when) — Federal-rights notice; Advantage trial/history questions; situation-specific answers (federal); [S11: Change Medigap policy](https://www.medicare.gov/health-drug-plans/medigap/ready-to-buy/change-policies) — Can I change my Medigap policy? (federal). These sources support why the fact matters; scheduling/deduplication and privacy choices are Daylight product policy, not statutory requirements.


<a id="rc08"></a>
## RC08 · Enrollment event/window

**Trigger / scope:** User requests a change/start outside an established reviewed window, or reports move, loss, plan termination, institutional stay, disaster or other potential event. **conditional · MVP.**

**Question:** What changed about your coverage?

**Why we ask: This can affect when you can enroll.**

**Controls:** Losing coverage; Moving; Plan ending/changing service area; Medicaid/Extra Help change; Another event + text; Nothing changed; Not sure. Every question also supports Not sure, Check later/Defer, Back and Ask. Something else retains brief text and requires confirmed extraction; no invented enum. RC29/RC30 are boundary controls, not automatically queued questions.

**Proposed schema:** `{"timing.event": "approved enum|other|unknown", "timing.eventDate": "date+precision|unknown", "timing.noticeDate": "date+precision|unknown if relevant"}`. These are design fields, not fields currently accepted by the guest backend.

**Dependencies:** RC03, RC04, RC07.

**Resolution:** Applicable event details are available for source-backed review, or window remains unknown.

**Ambiguity/contradiction:** Part B, MA/PDP and Medigap windows are separate. A doctor leaving a network is not automatically any generic SEP. Unknown notice date is not fabricated.

**Evidence:** Dated notice/event evidence; reviewed rule version and actual election period; no upload required in MVP. User-confirmed remains reported, never independently verified.

**Matching consequence:** Unknown holds enrollment-action readiness only; scoped browsing may proceed.

**Human-help reason:** Near/past deadline, disaster or exceptional facts: Medicare/SHINE; do not calculate a deadline from guesswork.

**Official support (retrieved October 22, 2026):** [S01: Joining a plan](https://www.medicare.gov/basics/get-started-with-medicare/get-more-coverage/joining-a-plan) — Am I eligible?; Initial Enrollment Period; Other enrollment periods (federal); [S17: Special Enrollment Periods](https://www.medicare.gov/basics/get-started-with-medicare/get-more-coverage/joining-a-plan/special-enrollment-periods) — Change where you live; lose coverage; Medicaid/Extra Help; special situations (federal). These sources support why the fact matters; scheduling/deduplication and privacy choices are Daylight product policy, not statutory requirements.


<a id="rc09"></a>
## RC09 · Current employment vs continuation

**Trigger / scope:** Q5 employer/retiree/COBRA or free text indicates job-related insurance, but source of coverage/current-work relationship unclear. **conditional · MVP.**

**Question:** Is this coverage from someone who is still working?

**Why we ask: Current work can affect your Medicare sign-up window.**

**Controls:** My current job; Spouse’s current job; Family member’s current job; Retiree coverage; COBRA; Other/Not sure. Every question also supports Not sure, Check later/Defer, Back and Ask. Something else retains brief text and requires confirmed extraction; no invented enum. RC29/RC30 are boundary controls, not automatically queued questions.

**Proposed schema:** `{"work.coverageKind": "self_current|spouse_current|family_current|retiree|COBRA|other|unknown"}`. These are design fields, not fields currently accepted by the guest backend.

**Dependencies:** RC07.

**Resolution:** Coverage kind/current work clarified or explicitly unresolved.

**Ambiguity/contradiction:** An employer name does not mean active-employment coverage; a stipend/individual policy may differ. Multiple jobs/plans remain separate.

**Evidence:** Benefits administrator confirmation of group/current-work status. User-confirmed remains reported, never independently verified.

**Matching consequence:** Unknown holds delay/payer-order advice; not a reason to suppress noncommercial plan options.

**Human-help reason:** Self-employed/individual reimbursement/multiple plans: benefits administrator/BCRC/SHINE.

**Official support (retrieved October 22, 2026):** [S04: Working past 65](https://www.medicare.gov/basics/get-started-with-medicare/medicare-basics/working-past-65) — Health insurance from a job; COBRA; Before you sign up (federal); [S05: Who pays first?](https://www.medicare.gov/health-drug-plans/coordination/who-pays-first) — Current/former group coverage; employer-size paths; Federal Program/TRICARE paths (federal); [S06: COBRA coverage](https://www.medicare.gov/basics/get-started-with-medicare/medicare-basics/working-past-65/cobra-coverage) — How does COBRA work with Medicare? (federal). These sources support why the fact matters; scheduling/deduplication and privacy choices are Daylight product policy, not statutory requirements.


<a id="rc10"></a>
## RC10 · Relevant employer size

**Trigger / scope:** Current group coverage plus payer-order question; age/basis known. Do not run age threshold for ESRD. **conditional · MVP.**

**Question:** Does the employer have 20 or more employees?

**Why we ask: Employer size can change which coverage pays first.**

**Controls:** Yes; No; Not sure. Every question also supports Not sure, Check later/Defer, Back and Ask. Something else retains brief text and requires confirmed extraction; no invented enum. RC29/RC30 are boundary controls, not automatically queued questions.

**Proposed schema:** `{"work.sizeBand": "under20|20to99|100plus|unknown", "work.multiEmployer": "yes|no|unknown"}`. These are design fields, not fields currently accepted by the guest backend.

**Dependencies:** RC06, RC09.

**Resolution:** Age-65 case uses 20 threshold; under-65 disability variant asks “100 or more employees?”; uncertain multi-employer facts remain held.

**Ambiguity/contradiction:** Do not use 20 universally; do not apply either shortcut to ESRD. Family-member coverage under disability needs exact review.

**Evidence:** Employer/benefits administrator size and group classification, not an LLM/company-web headcount guess. User-confirmed remains reported, never independently verified.

**Matching consequence:** Unresolved holds payer-order/delay conclusions; plan benefit comparison still possible with warnings.

**Human-help reason:** Multi-employer or ESRD: BCRC/SHINE; no automatic payer verdict.

**Official support (retrieved October 22, 2026):** [S05: Who pays first?](https://www.medicare.gov/health-drug-plans/coordination/who-pays-first) — Current/former group coverage; employer-size paths; Federal Program/TRICARE paths (federal); [S28: ESRD](https://www.medicare.gov/basics/end-stage-renal-disease) — Group coverage and coordination period (federal). These sources support why the fact matters; scheduling/deduplication and privacy choices are Daylight product policy, not statutory requirements.


<a id="rc11"></a>
## RC11 · Separate loss/job dates

**Trigger / scope:** Coverage/job ending or ended, COBRA/retiree transition, or prospective change needs loss chronology. **conditional · MVP.**

**Question:** When did the job end?

**Why we ask: Different end dates can change your sign-up window.**

**Controls:** Date selector with unknown parts allowed; Still working; Not sure. Every question also supports Not sure, Check later/Defer, Back and Ask. Something else retains brief text and requires confirmed extraction; no invented enum. RC29/RC30 are boundary controls, not automatically queued questions.

**Proposed schema:** `{"work.employmentEnd": "date+precision|still_working|unknown", "work.activeCoverageEnd": "separate date+precision|ongoing|unknown", "work.continuationEnd": "separate if relevant"}`. These are design fields, not fields currently accepted by the guest backend.

**Dependencies:** RC09.

**Resolution:** Ask approved child “When does the job-based health coverage end?” only if missing; save dates independently.

**Ambiguity/contradiction:** Do not substitute retirement, COBRA expiry, notice date or requested start for active group coverage loss. Ranges crossing a deadline stay uncertain.

**Evidence:** Employer/coverage notices or user’s dated report; actual documents only through an approved future secure path. User-confirmed remains reported, never independently verified.

**Matching consequence:** Missing dates hold transition/deadline advice; explain which exact check remains open.

**Human-help reason:** Potential gap/late enrollment: prompt official enrollment review, not automated cancellation.

**Official support (retrieved October 22, 2026):** [S03: When coverage starts](https://www.medicare.gov/basics/get-started-with-medicare/sign-up/when-does-medicare-coverage-start) — Initial Enrollment Period; Signing up for premium-free Part A later; Special Enrollment Period (federal); [S04: Working past 65](https://www.medicare.gov/basics/get-started-with-medicare/medicare-basics/working-past-65) — Health insurance from a job; COBRA; Before you sign up (federal); [S06: COBRA coverage](https://www.medicare.gov/basics/get-started-with-medicare/medicare-basics/working-past-65/cobra-coverage) — How does COBRA work with Medicare? (federal). These sources support why the fact matters; scheduling/deduplication and privacy choices are Daylight product policy, not statutory requirements.


<a id="rc12"></a>
## RC12 · Creditable drug coverage/gap

**Trigger / scope:** Part D is absent/ending/unknown and employer/retiree/military/other drug coverage might exist, or user proposes no drug coverage. **conditional · MVP.**

**Question:** Does your plan say its drug coverage is creditable?

**Why we ask: A gap in qualifying drug coverage can affect later costs.**

**Controls:** Yes, according to its notice; No; I have no drug coverage; Not sure. Every question also supports Not sure, Check later/Defer, Back and Ask. Something else retains brief text and requires confirmed extraction; no invented enum. RC29/RC30 are boundary controls, not automatically queued questions.

**Proposed schema:** `{"drugCoverage.creditableReport": "yes|no|none|unknown", "drugCoverage.lastCoveredDay": "date+precision|ongoing|unknown"}`. These are design fields, not fields currently accepted by the guest backend.

**Dependencies:** RC07, RC09.

**Resolution:** Notice status and relevant end date recorded or unresolved; no penalty amount invented.

**Ambiguity/contradiction:** No current prescriptions does not mean no need to consider D. The 63-day issue is not an MA/PDP election deadline or the eight-month Part B clock.

**Evidence:** Current written creditable-coverage notice and coverage dates; assistance status can change penalty analysis. User-confirmed remains reported, never independently verified.

**Matching consequence:** Unknown holds penalty/transition conclusions; no blanket no-D recommendation.

**Human-help reason:** Missing notice, gap, family-retiree risk: benefits administrator/Medicare/SHINE.

**Official support (retrieved October 22, 2026):** [S08: Creditable drug coverage](https://www.medicare.gov/health-drug-plans/part-d/basics/creditable-coverage) — Why do I need creditable coverage?; What you should do (federal); [S14: Help with drug costs](https://www.medicare.gov/basics/costs/help/drug-costs) — Who gets Extra Help automatically?; applying; wrong amount (federal). These sources support why the fact matters; scheduling/deduplication and privacy choices are Daylight product policy, not statutory requirements.


<a id="rc13"></a>
## RC13 · Retiree/family benefit consequences

**Trigger / scope:** Employer/union/retiree coverage exists and user considers joining outside MA/PDP or dropping group coverage. **conditional · MVP.**

**Question:** Could a change affect anyone else’s coverage?

**Why we ask: Some changes can affect family or retiree benefits.**

**Controls:** Administrator says yes; Administrator says no; I have not checked; Not sure. Every question also supports Not sure, Check later/Defer, Back and Ask. Something else retains brief text and requires confirmed extraction; no invented enum. RC29/RC30 are boundary controls, not automatically queued questions.

**Proposed schema:** `{"coordination.familyRisk": "yes|no|unchecked|unknown", "coordination.adminChecked": "reported date/source|unknown"}`. These are design fields, not fields currently accepted by the guest backend.

**Dependencies:** RC09.

**Resolution:** Administrator report recorded; unchecked remains a specific action item.

**Ambiguity/contradiction:** Joining an outside plan can have consequences beyond the beneficiary. Do not assume coverage can be restored.

**Evidence:** Benefits administrator’s plan-specific confirmation, ideally retained notice. User-confirmed remains reported, never independently verified.

**Matching consequence:** Unconfirmed holds recommended change/action; general comparison can remain available.

**Human-help reason:** Benefits administrator before any enrollment/cancellation; human help optional.

**Official support (retrieved October 22, 2026):** [S07: Retiree insurance](https://www.medicare.gov/basics/get-started-with-medicare/medicare-basics/working-past-65/retiree-insurance) — Drug coverage; check before making decisions (federal); [S08: Creditable drug coverage](https://www.medicare.gov/health-drug-plans/part-d/basics/creditable-coverage) — Why do I need creditable coverage?; What you should do (federal). These sources support why the fact matters; scheduling/deduplication and privacy choices are Daylight product policy, not statutory requirements.


<a id="rc14"></a>
## RC14 · HSA timing

**Trigger / scope:** User reports current-work coverage, Medicare deferral/retroactive A or specifically mentions HSA contributions. **conditional · MVP.**

**Question:** Are you or your employer adding money to an HSA?

**Why we ask: Medicare start dates can affect HSA contributions.**

**Controls:** Yes; No; Not sure. Every question also supports Not sure, Check later/Defer, Back and Ask. Something else retains brief text and requires confirmed extraction; no invented enum. RC29/RC30 are boundary controls, not automatically queued questions.

**Proposed schema:** `{"work.hsaContributions": "yes|no|unknown"}`. These are design fields, not fields currently accepted by the guest backend.

**Dependencies:** RC05, RC09.

**Resolution:** No ends the trigger; yes/unknown creates review task, never an automated tax instruction.

**Ambiguity/contradiction:** An HSA balance differs from current contributions. Do not request balance/account number or equate retirement date with Part A effective date.

**Evidence:** Actual Part A/benefit application dates and tax/benefits advice, not just a requested start month. User-confirmed remains reported, never independently verified.

**Matching consequence:** Holds HSA/tax timing advice; not all plan comparisons.

**Human-help reason:** Benefits/tax professional and SSA for retroactive-date implications.

**Official support (retrieved October 22, 2026):** [S03: When coverage starts](https://www.medicare.gov/basics/get-started-with-medicare/sign-up/when-does-medicare-coverage-start) — Initial Enrollment Period; Signing up for premium-free Part A later; Special Enrollment Period (federal); [S04: Working past 65](https://www.medicare.gov/basics/get-started-with-medicare/medicare-basics/working-past-65) — Health insurance from a job; COBRA; Before you sign up (federal). These sources support why the fact matters; scheduling/deduplication and privacy choices are Daylight product policy, not statutory requirements.


<a id="rc15"></a>
## RC15 · Florida Medigap purchase window

**Trigger / scope:** Original+Medigap purchase/replacement path requested; age, basis, Part B start or qualifying group-loss dates are missing or not reviewed. **conditional · MVP.**

**Question:** When did your Part B coverage begin?

**Why we ask: This can affect your Medigap purchase rights.**

**Controls:** Month/year selector; Not sure. Every question also supports Not sure, Check later/Defer, Back and Ask. Something else retains brief text and requires confirmed extraction; no invented enum. RC29/RC30 are boundary controls, not automatically queued questions.

**Proposed schema:** `{"medigap.partBStart": "reference enrollment date, no duplicate fact", "medigap.rightsReview": "pending|reviewed; never LLM-qualified"}`. These are design fields, not fields currently accepted by the guest backend.

**Dependencies:** RC02, RC05, RC06, RC11.

**Resolution:** Reuse dates already confirmed; evaluate federal and Florida candidates separately. Resolution is facts sufficient for expert review, not guaranteed issue confirmed.

**Ambiguity/contradiction:** Florida six-month and qualifying group-termination two-month provisions differ from federal event-specific rights. Do not promise every policy/price or apply Florida elsewhere.

**Evidence:** Florida residency, age/basis, B dates and relevant termination evidence; approved jurisdiction/year rule receipt. User-confirmed remains reported, never independently verified.

**Matching consequence:** Unreviewed rights hold issueability/underwriting-free/quote eligibility claims; public Medigap benefit explanations remain possible.

**Human-help reason:** Licensed Florida expert/SHINE/OIR when window/rights uncertain.

**Official support (retrieved October 22, 2026):** [S10: Medigap basics](https://www.medicare.gov/health-drug-plans/medigap/basics) — Get Medigap Basics; Open Enrollment (federal); [S12: Florida Statutes 627.6741](https://www.leg.state.fl.us/Statutes/index.cfm?App_mode=Display_Statute&Search_String=&URL=0600-0699/0627/Sections/0627.6741.html) — 2026 edition, subsection (1)(a)1 and (1)(a)2; (1)(b) (Florida); [S13: Florida Medicare Supplement oversight](https://www.floir.gov/life-health/medicare-supplement) — Overview; CHOICES rate search; FAQs (Florida). These sources support why the fact matters; scheduling/deduplication and privacy choices are Daylight product policy, not statutory requirements.


<a id="rc16"></a>
## RC16 · Trial/guaranteed-issue history

**Trigger / scope:** Current/recent MA plus interest in Original+Medigap, lost supplement, plan termination/move or alleged insurer misconduct. **conditional · MVP.**

**Question:** Was this your first Medicare Advantage plan?

**Why we ask: Your coverage history may affect Medigap rights.**

**Controls:** Yes; No; Not sure. Every question also supports Not sure, Check later/Defer, Back and Ask. Something else retains brief text and requires confirmed extraction; no invented enum. RC29/RC30 are boundary controls, not automatically queued questions.

**Proposed schema:** `{"medigap.firstMA": "yes|no|unknown", "medigap.maJoinDate": "date+precision|unknown", "medigap.hadPriorPolicy": "yes|no|unknown", "medigap.eventEvidence": "notice type/date|unknown"}`. These are design fields, not fields currently accepted by the guest backend.

**Dependencies:** RC07, RC08, RC15.

**Resolution:** Only missing approved child questions asked: “When did it start?” and “Did you have Medigap before it?” Events reach specialist review.

**Ambiguity/contradiction:** First MA at initial Medicare eligibility and dropping Medigap to try MA are distinct trial patterns; plan letters/availability differ. Never convert within-12-month report alone to guaranteed rights.

**Evidence:** Prior policy/join/end dates, reason for loss and dated notices; rule-specific source and expert receipt. User-confirmed remains reported, never independently verified.

**Matching consequence:** Holds guaranteed-issue/transition confidence; does not hide Original/MA alternatives.

**Human-help reason:** Licensed Florida reviewer/SHINE before relinquishing current coverage.

**Official support (retrieved October 22, 2026):** [S09: When can I buy Medigap?](https://www.medicare.gov/health-drug-plans/medigap/ready-to-buy/when) — Federal-rights notice; Advantage trial/history questions; situation-specific answers (federal); [S11: Change Medigap policy](https://www.medicare.gov/health-drug-plans/medigap/ready-to-buy/change-policies) — Can I change my Medigap policy? (federal); [S12: Florida Statutes 627.6741](https://www.leg.state.fl.us/Statutes/index.cfm?App_mode=Display_Statute&Search_String=&URL=0600-0699/0627/Sections/0627.6741.html) — 2026 edition, subsection (1)(a)1 and (1)(a)2; (1)(b) (Florida). These sources support why the fact matters; scheduling/deduplication and privacy choices are Daylight product policy, not statutory requirements.


<a id="rc17"></a>
## RC17 · Existing Medigap replacement

**Trigger / scope:** User already has Medigap and wants another supplement/carrier or is considering dropping it. **conditional · MVP.**

**Question:** Are you replacing an existing Medigap policy?

**Why we ask: You may not have the same rights to buy it again.**

**Controls:** Yes; No, keeping it; Not sure. Every question also supports Not sure, Check later/Defer, Back and Ask. Something else retains brief text and requires confirmed extraction; no invented enum. RC29/RC30 are boundary controls, not automatically queued questions.

**Proposed schema:** `{"medigap.replacementIntent": "replace|keep|unknown", "medigap.currentPolicy": "letter/carrier/version report|unknown"}`. These are design fields, not fields currently accepted by the guest backend.

**Dependencies:** RC07, RC15.

**Resolution:** Keep means no replacement intake; replace/unknown retains current coverage and review task.

**Ambiguity/contradiction:** Annual MA/PDP open enrollment is not universal Medigap open enrollment. Do not demand diagnosis/underwriting history in this readiness chat.

**Evidence:** Current policy letter, issue history and new insurer’s actual acceptance/rate; final replacement rules separate. User-confirmed remains reported, never independently verified.

**Matching consequence:** Holds accepted/purchasable replacement claim and cancellation steps, not standardized-benefit browsing.

**Human-help reason:** Licensed reviewer/insurer before cancellation; explain review is optional, not a sales gate.

**Official support (retrieved October 22, 2026):** [S11: Change Medigap policy](https://www.medicare.gov/health-drug-plans/medigap/ready-to-buy/change-policies) — Can I change my Medigap policy? (federal); [S12: Florida Statutes 627.6741](https://www.leg.state.fl.us/Statutes/index.cfm?App_mode=Display_Statute&Search_String=&URL=0600-0699/0627/Sections/0627.6741.html) — 2026 edition, subsection (1)(a)1 and (1)(a)2; (1)(b) (Florida); [S13: Florida Medicare Supplement oversight](https://www.floir.gov/life-health/medicare-supplement) — Overview; CHOICES rate search; FAQs (Florida). These sources support why the fact matters; scheduling/deduplication and privacy choices are Daylight product policy, not statutory requirements.


<a id="rc18"></a>
## RC18 · Assistance status without financial intake

**Trigger / scope:** Subsidy-adjusted costs, a reported Medicaid program, affordability concern or explicit help request makes program status consequential. **conditional · MVP.**

**Question:** Do you get help with Medicare costs now?

**Why we ask: Assistance can change what you pay.**

**Controls:** Medicaid; Extra Help; Help paying Part B; SSI; None known; Not sure; Prefer not to say. Every question also supports Not sure, Check later/Defer, Back and Ask. Something else retains brief text and requires confirmed extraction; no invented enum. RC29/RC30 are boundary controls, not automatically queued questions.

**Proposed schema:** `{"assistance.programReports": "set of enums|unknown|declined", "assistance.effectiveYear": "YYYY|unknown"}`. These are design fields, not fields currently accepted by the guest backend.

**Dependencies:** RC01, RC03.

**Resolution:** Current program reports/unknown/declined recorded; offer official application support, not a local eligibility decision.

**Ambiguity/contradiction:** Medicaid, QMB/MSP, Extra Help and SSI are distinct. Program amount/year can change; no bank, tax-return or account collection here.

**Evidence:** Current benefit/decision notice or official program check with separate permission; state/SSA determines eligibility. User-confirmed remains reported, never independently verified.

**Matching consequence:** Unknown holds personalized subsidy-adjusted costs/SNP eligibility, not unsubsidized labeled scenarios.

**Human-help reason:** SHINE/state Medicaid/SSA; finances submitted directly through approved official process.

**Official support (retrieved October 22, 2026):** [S14: Help with drug costs](https://www.medicare.gov/basics/costs/help/drug-costs) — Who gets Extra Help automatically?; applying; wrong amount (federal); [S15: Medicare Savings Programs](https://www.medicare.gov/basics/costs/help/medicare-savings-programs) — How to qualify; Qualified Medicare Beneficiary (federal/state); [S29: Applying for Extra Help](https://www.ssa.gov/medicare/part-d-extra-help) — Apply online; documents (federal). These sources support why the fact matters; scheduling/deduplication and privacy choices are Daylight product policy, not statutory requirements.


<a id="rc19"></a>
## RC19 · SNP-specific qualification

**Trigger / scope:** User asks about an SNP or volunteers Medicaid/qualifying institutional/chronic circumstances and a supported candidate actually requires them. **conditional · MVP flags/referral; detailed SNP matching future.**

**Question:** Has anyone confirmed you qualify for this type of special-needs plan?

**Why we ask: These plans have additional enrollment requirements.**

**Controls:** Yes, current notice/plan confirmation; No; Not sure; I do not want to explore these plans. Every question also supports Not sure, Check later/Defer, Back and Ask. Something else retains brief text and requires confirmed extraction; no invented enum. RC29/RC30 are boundary controls, not automatically queued questions.

**Proposed schema:** `{"snp.reportedCategory": "dual|chronic|institutional|unknown", "snp.verification": "pending|verified evidence ref only"}`. These are design fields, not fields currently accepted by the guest backend.

**Dependencies:** RC02, RC04, RC18.

**Resolution:** Category and evidence routed to plan/state review; decline closes this optional exploration without erasing known assistance.

**Ambiguity/contradiction:** Extra Help alone is not full Medicaid or proof of D-SNP alignment; a diagnosis mention is not verified C-SNP eligibility. No exhaustive diagnosis questionnaire.

**Evidence:** Applicable state/plan eligibility proof, A/B, area and alignment requirements for exact plan/year. User-confirmed remains reported, never independently verified.

**Matching consequence:** Only SNP eligibility/fit held; other available paths not suppressed.

**Human-help reason:** Plan/state/qualified reviewer for exact criteria.

**Official support (retrieved October 22, 2026):** [S16: Special Needs Plans](https://www.medicare.gov/health-drug-plans/health-plans/your-health-plan-options/SNP) — Who can join an SNP?; eligibility requirements (federal/state/plan); [S17: Special Enrollment Periods](https://www.medicare.gov/basics/get-started-with-medicare/get-more-coverage/joining-a-plan/special-enrollment-periods) — Change where you live; lose coverage; Medicaid/Extra Help; special situations (federal). These sources support why the fact matters; scheduling/deduplication and privacy choices are Daylight product policy, not statutory requirements.


<a id="rc20"></a>
## RC20 · Seasonal/routine travel

**Trigger / scope:** Q8 another-state/outside-US/unknown or moving/seasonal facts make care locations material to requested provider/travel fit. **conditional · MVP.**

**Question:** Where will you need routine care away from home?

**Why we ask: Routine care and emergency care can have different coverage.**

**Controls:** Another U.S. state + location; Outside the U.S. + optional country; Emergency travel cover only; Not sure. Every question also supports Not sure, Check later/Defer, Back and Ask. Something else retains brief text and requires confirmed extraction; no invented enum. RC29/RC30 are boundary controls, not automatically queued questions.

**Proposed schema:** `{"travel.routineLocations": "bounded public-location list", "travel.need": "routine|emergency|both|unknown"}`. These are design fields, not fields currently accepted by the guest backend.

**Dependencies:** RC02.

**Resolution:** Routine/emergency need and locations clarified or travel-fit limitation retained.

**Ambiguity/contradiction:** Seasonal stay does not automatically change permanent home. A PPO label or foreign emergency benefit does not promise routine access.

**Evidence:** Plan EOC/network/travel-benefit terms for year; provider/location checks. User-confirmed remains reported, never independently verified.

**Matching consequence:** Unknown holds travel-fit claims only; no automated Original-over-Advantage preference.

**Human-help reason:** Complex residency/long overseas stay: plan/SHINE; travel insurance referral only if requested.

**Official support (retrieved October 22, 2026):** [S18: Travel outside the U.S.](https://www.medicare.gov/coverage/travel-outside-the-u.s.) — Description; Coverage details (federal/plan); [S19: Advantage provider networks](https://www.medicare.gov/publications/11941-Understanding-Your-Medicare-Advantage-Plan.pdf) — pp. 1–3, provider directories and checking with providers/plan (federal/plan). These sources support why the fact matters; scheduling/deduplication and privacy choices are Daylight product policy, not statutory requirements.


<a id="rc21"></a>
## RC21 · Exact provider identity/location

**Trigger / scope:** Provider-fit requested and Q6 names are unresolved, ambiguous, location-free, or source/network result unavailable. **conditional · MVP.**

**Question:** Which location do you use for this doctor?

**Why we ask: The office location can affect the network check.**

**Controls:** Office/practice + city; Choose a verified identity candidate; Add later; No longer needed. Every question also supports Not sure, Check later/Defer, Back and Ask. Something else retains brief text and requires confirmed extraction; no invented enum. RC29/RC30 are boundary controls, not automatically queued questions.

**Proposed schema:** `{"providers.entities": "id,name,public practice/location,priority,report status", "providers.networkChecks": "plan/year/as-of/evidence, separate"}`. These are design fields, not fields currently accepted by the guest backend.

**Dependencies:** RC02, RC03.

**Resolution:** User confirms the exact provider/location; identity resolution remains separate from network verification.

**Ambiguity/contradiction:** Do not choose among duplicate names by LLM confidence. Hospital/facility and doctor may need distinct checks; Medicare acceptance is not MA participation.

**Evidence:** Accepted directory plus exact plan contract/year and dated plan/provider confirmation; public provider ID alone insufficient. User-confirmed remains reported, never independently verified.

**Matching consequence:** Missing identity holds fit for that provider. Missing network source is a system limitation, not a negative score or another user question.

**Human-help reason:** Conflicting directories/ongoing treatment: plan/provider and optional human.

**Official support (retrieved October 22, 2026):** [S19: Advantage provider networks](https://www.medicare.gov/publications/11941-Understanding-Your-Medicare-Advantage-Plan.pdf) — pp. 1–3, provider directories and checking with providers/plan (federal/plan). These sources support why the fact matters; scheduling/deduplication and privacy choices are Daylight product policy, not statutory requirements.


<a id="rc22"></a>
## RC22 · Exact prescription identity

**Trigger / scope:** Drug-fit/cost requested and medication string lacks a unique ingredient/brand, strength or form; preserve original wording. **conditional · MVP.**

**Question:** Which version of this prescription do you take?

**Why we ask: Strength and form can change the coverage check.**

**Controls:** Name/strength/form fields or verified candidates; Not sure; Add later; No longer taking. Every question also supports Not sure, Check later/Defer, Back and Ask. Something else retains brief text and requires confirmed extraction; no invented enum. RC29/RC30 are boundary controls, not automatically queued questions.

**Proposed schema:** `{"medications.entities": "id,originalText,ingredient/brand,strength,form,RxNorm candidate/user confirmation", "medications.active": "yes|no|unknown"}`. These are design fields, not fields currently accepted by the guest backend.

**Dependencies:** RC03.

**Resolution:** Confirmed identity tuple or explicit unresolved entity; one prompt per grouped missing tuple, not every field as another page.

**Ambiguity/contradiction:** Similar names, extended-release vs immediate-release, salt/route and brand alternatives must not be silently substituted. Do not recommend medication changes.

**Evidence:** User confirmation plus accepted terminology mapping and plan formulary identity/version; exact match requires live validated data. User-confirmed remains reported, never independently verified.

**Matching consequence:** Unknown holds that drug’s coverage/price, not an inferred uncovered verdict or all general plan information.

**Human-help reason:** Bottle/prescriber/pharmacist clarification; no image upload or medical advice required.

**Official support (retrieved October 22, 2026):** [S20: RxNorm overview](https://www.nlm.nih.gov/research/umls/rxnorm/overview.html) — Normalized names: ingredient, strength and dose form (technical/federal); [S21: How drug plans work](https://www.medicare.gov/health-drug-plans/part-d/what-drug-plans-cover/how-drug-plans-work) — Formularies; pharmacy network (federal/plan). These sources support why the fact matters; scheduling/deduplication and privacy choices are Daylight product policy, not statutory requirements.


<a id="rc23"></a>
## RC23 · Supply and pharmacy

**Trigger / scope:** A drug-cost check is requested and days supply/quantity/fill channel or exact pharmacy is missing. **conditional · MVP.**

**Question:** How do you usually fill this prescription?

**Why we ask: Supply and pharmacy can change the price.**

**Controls:** Quantity + days supply; pharmacy/location; Mail order; Not sure; Add later. Every question also supports Not sure, Check later/Defer, Back and Ask. Something else retains brief text and requires confirmed extraction; no invented enum. RC29/RC30 are boundary controls, not automatically queued questions.

**Proposed schema:** `{"medications.fill": "quantity,unit,daysSupply|unknown", "pharmacies.preferred": "exact public identity/location|unknown", "pharmacies.channel": "retail|mail|specialty|unknown"}`. These are design fields, not fields currently accepted by the guest backend.

**Dependencies:** RC22.

**Resolution:** Required pricing inputs complete or the cost dimension explicitly withheld.

**Ambiguity/contradiction:** Dose instructions and dispensed quantity differ. Preferred vs standard network, specialty channels and travel pharmacies need evidence, not guesses.

**Evidence:** Accepted plan pharmacy-network/pricing files for plan/year/fill tuple; user preference does not prove participation. User-confirmed remains reported, never independently verified.

**Matching consequence:** Missing inputs hold personal drug estimate only; a flat copay or premium must not stand in for total cost.

**Human-help reason:** Pharmacist/plan when fill pattern or specialty pharmacy unclear.

**Official support (retrieved October 22, 2026):** [S21: How drug plans work](https://www.medicare.gov/health-drug-plans/part-d/what-drug-plans-cover/how-drug-plans-work) — Formularies; pharmacy network (federal/plan); [S24: Medicare costs](https://www.medicare.gov/basics/costs/medicare-costs) — Costs for Parts A/B/C/D and Medigap; year-specific tables (federal/plan). These sources support why the fact matters; scheduling/deduplication and privacy choices are Daylight product policy, not statutory requirements.


<a id="rc24"></a>
## RC24 · Restrictions and Part B/D boundary

**Trigger / scope:** Validated source flags PA/ST/quantity restrictions, administration setting is ambiguous, or user reports a current exception/coverage problem. **conditional · MVP.**

**Question:** Is this given at a clinic or filled at a pharmacy?

**Why we ask: Some medicines use different Medicare coverage rules.**

**Controls:** At a clinic; At a pharmacy; Both/Not sure. Every question also supports Not sure, Check later/Defer, Back and Ask. Something else retains brief text and requires confirmed extraction; no invented enum. RC29/RC30 are boundary controls, not automatically queued questions.

**Proposed schema:** `{"medications.setting": "clinic|pharmacy|both|unknown", "medications.restrictions": "source-derived, not user-guessed", "medications.currentApprovalReport": "yes|no|unknown if material"}`. These are design fields, not fields currently accepted by the guest backend.

**Dependencies:** RC22, RC23.

**Resolution:** Setting/reported problem preserved; restriction approval remains separate pending plan/prescriber confirmation.

**Ambiguity/contradiction:** An old authorization does not establish approval under a new plan. Do not ask users to diagnose which Medicare part pays or waive requirements.

**Evidence:** Plan formulary/EOC, indication/setting where officially necessary, and prescriber/plan decision; minimum health context only with consent. User-confirmed remains reported, never independently verified.

**Matching consequence:** Restricted coverage displayed as conditional; unsupported Part-B drug costing withheld instead of marked not covered.

**Human-help reason:** Prescriber/pharmacist/plan for approvals, exceptions or continuity issues.

**Official support (retrieved October 22, 2026):** [S22: Drug plan rules](https://www.medicare.gov/health-drug-plans/part-d/what-drug-plans-cover/plan-rules) — Prior authorization; step therapy; quantity limits (federal/plan); [S23: Outpatient prescription drugs](https://www.medicare.gov/coverage/prescription-drugs-outpatient) — Description; Coverage details (federal). These sources support why the fact matters; scheduling/deduplication and privacy choices are Daylight product policy, not statutory requirements.


<a id="rc25"></a>
## RC25 · Affordability vs preference

**Trigger / scope:** Cost priority or numeric budget request is material; Q9 cost preference alone does not establish affordability or total annual spending. **conditional · MVP.**

**Question:** Is there a monthly amount you want to stay under?

**Why we ask: A low plan premium is not the whole cost.**

**Controls:** Optional amount/range + what it includes; No fixed limit; Not sure; Prefer not to say. Every question also supports Not sure, Check later/Defer, Back and Ask. Something else retains brief text and requires confirmed extraction; no invented enum. RC29/RC30 are boundary controls, not automatically queued questions.

**Proposed schema:** `{"cost.monthlyLimit": "number/range|unknown|declined", "cost.limitBasis": "all recurring premiums|plan only|unknown", "cost.utilizationAssumptions": "explicit scenario, not inferred"}`. These are design fields, not fields currently accepted by the guest backend.

**Dependencies:** RC03, RC18.

**Resolution:** Budget basis acknowledged or unknown; do not force financial disclosure.

**Ambiguity/contradiction:** Include/exclude Part B, Medigap, drug/medical use and possible income adjustments explicitly. No income/tax documents here; unknown medical use prevents a guaranteed total.

**Evidence:** Year-specific accepted premium/benefit/drug/rate sources plus clearly dated assumptions; estimated vs binding quote separated. User-confirmed remains reported, never independently verified.

**Matching consequence:** Unknown budget limits affordability assessment only; absent source/care-use assumptions holds personalized total/ranking, not all browsing.

**Human-help reason:** SHINE for cost assistance; SSA for income-adjustment questions; clinician never inferred by spending.

**Official support (retrieved October 22, 2026):** [S24: Medicare costs](https://www.medicare.gov/basics/costs/medicare-costs) — Costs for Parts A/B/C/D and Medigap; year-specific tables (federal/plan); [S14: Help with drug costs](https://www.medicare.gov/basics/costs/help/drug-costs) — Who gets Extra Help automatically?; applying; wrong amount (federal); [S15: Medicare Savings Programs](https://www.medicare.gov/basics/costs/help/medicare-savings-programs) — How to qualify; Qualified Medicare Beneficiary (federal/state). These sources support why the fact matters; scheduling/deduplication and privacy choices are Daylight product policy, not statutory requirements.


<a id="rc26"></a>
## RC26 · Military/veterans coordination

**Trigger / scope:** Q5 military category or free text indicates VA, TRICARE, CHAMPVA or another federal program without exact program context. **conditional · MVP.**

**Question:** Which military or veterans’ coverage do you have?

**Why we ask: These programs work with Medicare in different ways.**

**Controls:** VA health care; TRICARE For Life; Other TRICARE; CHAMPVA; Another program; Not sure. Every question also supports Not sure, Check later/Defer, Back and Ask. Something else retains brief text and requires confirmed extraction; no invented enum. RC29/RC30 are boundary controls, not automatically queued questions.

**Proposed schema:** `{"coordination.federalProgram": "enum|unknown", "coordination.offSystemCare": "reported need|unknown"}`. These are design fields, not fields currently accepted by the guest backend.

**Dependencies:** RC04, RC12.

**Resolution:** Program classified for correct official referral; unresolved stays unknown.

**Ambiguity/contradiction:** VA is not TRICARE. Do not universally advise joining/dropping D, dropping B or adding Medigap; family consequences may matter.

**Evidence:** Relevant program/plan eligibility and coordination guidance; no service/membership identifiers. User-confirmed remains reported, never independently verified.

**Matching consequence:** Unresolved holds coordination and recommended change conclusions, not neutral education.

**Human-help reason:** VA/TRICARE/program administrator/BCRC/SHINE for exact arrangement.

**Official support (retrieved October 22, 2026):** [S05: Who pays first?](https://www.medicare.gov/health-drug-plans/coordination/who-pays-first) — Current/former group coverage; employer-size paths; Federal Program/TRICARE paths (federal); [S25: VA and other insurance](https://www.va.gov/resources/va-health-care-and-other-insurance/) — VA with Medicare; using each benefit (federal). These sources support why the fact matters; scheduling/deduplication and privacy choices are Daylight product policy, not statutory requirements.


<a id="rc27"></a>
## RC27 · Material exception/continuity

**Trigger / scope:** User/notice reports ESRD coordination, institutional stay, disaster, plan misconduct/termination, imminent coverage/refill gap or another source-listed exception. Do not screen everyone for every condition. **conditional · MVP recognition/referral; rare-case automation future.**

**Question:** Is there a coverage interruption you need help with now?

**Why we ask: An immediate gap may need a different next step.**

**Controls:** Yes + brief optional detail; No; Not sure; I want human help. Every question also supports Not sure, Check later/Defer, Back and Ask. Something else retains brief text and requires confirmed extraction; no invented enum. RC29/RC30 are boundary controls, not automatically queued questions.

**Proposed schema:** `{"exceptions.reported": "approved event enum + minimal wording", "exceptions.urgency": "reported|unknown", "exceptions.review": "pending evidence"}`. These are design fields, not fields currently accepted by the guest backend.

**Dependencies:** RC08.

**Resolution:** Route only to approved event child or unresolved human review; no new LLM-generated insurance branch.

**Ambiguity/contradiction:** Never translate serious illness to SNP eligibility, presume ESRD prevents MA enrollment, or infer an exception from vague urgency. No clinical triage/medical recommendation.

**Evidence:** Event-specific official source/notice; reviewed exception adapter. Rare unsupported events end in a documented human/source check. User-confirmed remains reported, never independently verified.

**Matching consequence:** Holds only affected timing/coordination/continuity assurances; no false safety guarantee.

**Human-help reason:** Medicare/SHINE and relevant plan/provider; no automatic external message.

**Official support (retrieved October 22, 2026):** [S17: Special Enrollment Periods](https://www.medicare.gov/basics/get-started-with-medicare/get-more-coverage/joining-a-plan/special-enrollment-periods) — Change where you live; lose coverage; Medicaid/Extra Help; special situations (federal); [S22: Drug plan rules](https://www.medicare.gov/health-drug-plans/part-d/what-drug-plans-cover/plan-rules) — Prior authorization; step therapy; quantity limits (federal/plan); [S28: ESRD](https://www.medicare.gov/basics/end-stage-renal-disease) — Group coverage and coordination period (federal). These sources support why the fact matters; scheduling/deduplication and privacy choices are Daylight product policy, not statutory requirements.


<a id="rc28"></a>
## RC28 · Conflicting or ambiguous proposed facts

**Trigger / scope:** Same person/period has mutually exclusive confirmed reports, unconfirmed text interpretation, or a result conflicts with the profile. **integrity_guard · MVP.**

**Question:** Which detail should we use?

**Why we ask: These answers lead to different checks.**

**Controls:** Explicit existing fact A; Explicit existing fact B; They apply at different times + dates; Neither + text; Not sure. Every question also supports Not sure, Check later/Defer, Back and Ask. Something else retains brief text and requires confirmed extraction; no invented enum. RC29/RC30 are boundary controls, not automatically queued questions.

**Proposed schema:** `{"integrity.conflict": "field/value refs, not deleted facts", "integrity.resolution": "confirmed replacement link|unknown"}`. These are design fields, not fields currently accepted by the guest backend.

**Dependencies:** None; integrity guards run before dependent checks.

**Resolution:** One explicit resolution or defer; one clarification retry maximum, then held. Facts at different times may both remain valid.

**Ambiguity/contradiction:** A+B membership and MA are not intrinsically inconsistent. Do not silently pick newer-looking text or AI confidence; preserve history and prior confirmed answers.

**Evidence:** User confirmation for report resolution; independent evidence still separately required for coverage truth. User-confirmed remains reported, never independently verified.

**Matching consequence:** Only dependent capabilities held; no favorable default/ranking.

**Human-help reason:** Unresolvable conflict or official notice disagreement: qualified human with user-controlled summary.

**Official support (retrieved October 22, 2026):** [S01: Joining a plan](https://www.medicare.gov/basics/get-started-with-medicare/get-more-coverage/joining-a-plan) — Am I eligible?; Initial Enrollment Period; Other enrollment periods (federal); [S26: Caregiver permission](https://www.medicare.gov/basics/get-started-with-medicare/using-medicare/5-tips-for-using-medicare) — Tip 2: permission to talk to someone trusted (federal). These sources support why the fact matters; scheduling/deduplication and privacy choices are Daylight product policy, not statutory requirements.


<a id="rc29"></a>
## RC29 · Source/data capability guard

**Trigger / scope:** Rule/source missing, stale, future-year mismatched, expert review absent, API unavailable, acceptance registry pending, or requested capability unsupported. **system_no_question · MVP.**

**Question:** No question: show the specific unavailable check.

**Why we ask: Your answers cannot replace a missing source check.**

**Controls:** See limitations; Review saved answers; See labeled samples; Optional human help. Every question also supports Not sure, Check later/Defer, Back and Ask. Something else retains brief text and requires confirmed extraction; no invented enum. RC29/RC30 are boundary controls, not automatically queued questions.

**Proposed schema:** `{"capabilities.state": "not_supported|data_held|needs_facts|ready_for_scoped_check", "sources.receipt": "manifest/code/rule digest + approved review; null remains held"}`. These are design fields, not fields currently accepted by the guest backend.

**Dependencies:** None; integrity guards run before dependent checks.

**Resolution:** End affected data check with evidence-based state; do not collect irrelevant extra facts to conceal unavailable data.

**Ambiguity/contradiction:** A technically downloaded file or accurate LLM explanation is not an accepted consumer release. 2026 facts must not be relabeled 2027.

**Evidence:** Named review receipts for actual release/code/rules, effective year/scope, provider/formulary/rate evidence as applicable. User-confirmed remains reported, never independently verified.

**Matching consequence:** Capabilities held independently. Current registry is pending, so readiness facts cannot release personalized matches.

**Human-help reason:** User may choose SHINE or official source assistance; no claim Daylight human transfer is implemented.

**Official support (retrieved October 22, 2026):** [S01: Joining a plan](https://www.medicare.gov/basics/get-started-with-medicare/get-more-coverage/joining-a-plan) — Am I eligible?; Initial Enrollment Period; Other enrollment periods (federal); [S13: Florida Medicare Supplement oversight](https://www.floir.gov/life-health/medicare-supplement) — Overview; CHOICES rate search; FAQs (Florida); [S19: Advantage provider networks](https://www.medicare.gov/publications/11941-Understanding-Your-Medicare-Advantage-Plan.pdf) — pp. 1–3, provider directories and checking with providers/plan (federal/plan); [S21: How drug plans work](https://www.medicare.gov/health-drug-plans/part-d/what-drug-plans-cover/how-drug-plans-work) — Formularies; pharmacy network (federal/plan). These sources support why the fact matters; scheduling/deduplication and privacy choices are Daylight product policy, not statutory requirements.


<a id="rc30"></a>
## RC30 · Final plan-specific review

**Trigger / scope:** Future user selects a plan and requests application/action. Never part of the initial readiness question queue. **post_selection_not_queue · Future; separate final gate.**

**Question:** Confirm the final plan and coverage dates before applying.

**Why we ask: An application needs a separate plan-specific review.**

**Controls:** Review plan/EOC/effective date; Confirm details through authorized process; Keep researching. Every question also supports Not sure, Check later/Defer, Back and Ask. Something else retains brief text and requires confirmed extraction; no invented enum. RC29/RC30 are boundary controls, not automatically queued questions.

**Proposed schema:** `{"application.readiness": "separate future state; no Medicare IDs in research profile"}`. These are design fields, not fields currently accepted by the guest backend.

**Dependencies:** RC29.

**Resolution:** Official/plan eligibility and plan-specific confirmations, consent and application permissions completed through separately authorized workflow.

**Ambiguity/contradiction:** Readiness report and source-reviewed comparison are not enrollment, legal eligibility or approved exceptions. Never cancel old coverage from a suggested match.

**Evidence:** Exact plan/version/year, costs, providers/drugs/restrictions, election period, transition, official enrollment facts and user action approval. User-confirmed remains reported, never independently verified.

**Matching consequence:** Application/action held; comparison remains scoped and reversible.

**Human-help reason:** Licensed/official enrollment help where needed; optional self-service remains possible when supported.

**Official support (retrieved October 22, 2026):** [S01: Joining a plan](https://www.medicare.gov/basics/get-started-with-medicare/get-more-coverage/joining-a-plan) — Am I eligible?; Initial Enrollment Period; Other enrollment periods (federal); [S09: When can I buy Medigap?](https://www.medicare.gov/health-drug-plans/medigap/ready-to-buy/when) — Federal-rights notice; Advantage trial/history questions; situation-specific answers (federal); [S19: Advantage provider networks](https://www.medicare.gov/publications/11941-Understanding-Your-Medicare-Advantage-Plan.pdf) — pp. 1–3, provider directories and checking with providers/plan (federal/plan); [S22: Drug plan rules](https://www.medicare.gov/health-drug-plans/part-d/what-drug-plans-cover/plan-rules) — Prior authorization; step therapy; quantity limits (federal/plan). These sources support why the fact matters; scheduling/deduplication and privacy choices are Daylight product policy, not statutory requirements.
