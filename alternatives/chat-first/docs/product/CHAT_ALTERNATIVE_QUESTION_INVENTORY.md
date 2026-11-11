# Daylight question inventory · chat alternative

Snapshot of the current on-disk application, 23 October 2026. This inventory was written before alternative implementation. No new research or Medicare facts. Original app remains on port 8890.

## Meaning and source status

T01–T10 are implemented baseline reports in `ten-state.js`; RC01–RC28 are existing conditional input definitions in `readiness-content.json` with scheduling/merging in `readiness-core.js`. Their 29 references in `READINESS_SOURCES.md` are **research-only, not domain-approved policy**. All answers are user reports or explicit unknowns; none verify eligibility, provider/drug coverage, prices, rights or personal fit. RC29 is a system missing-data guard; RC30 is a future application gate. Neither is an intake question.

## Ten baseline questions

### T01 · What would you like help with today?

**Exact question:** What would you like help with today?

**Options:** Understand Medicare; Find coverage; Review existing coverage; Something else

**Why:** Your goal tells Daylight what to explain and what to emphasize. We will work through your situation, needs and priorities in ten questions.

**Fields:** `intent.goal`, `intent.goalDetail`.

**Trigger / skip / dedup:** Current app asks this once in the ten-screen route. Alternative reuses a confirmed report supplied earlier, asks only missing fields, and accepts unknown/defer. Something else retains optional wording; an unresolved goal is not an invented insurance route.

**Matching effect:** Prepares reported inputs and explanation preferences only. Existing plan-validation/personal ranking gates remain held.

**Status:** Baseline UI/state/persistence implemented; no independent source/coverage verification.

### T02 · How familiar are you with Medicare?

**Exact question:** How familiar are you with Medicare?

**Options:** New to Medicare; Know a little; Comfortable with the basics; Not sure yet

**Why:** This sets how much explanation you see. It changes the detail, not the questions or the facts we need.

**Fields:** `knowledge.general`.

**Trigger / skip / dedup:** Current app asks this once in the ten-screen route. Alternative reuses a confirmed report supplied earlier, asks only missing fields, and accepts unknown/defer. No quiz. Not sure yet preserves the global unknown-answer requirement. Familiarity affects explanation detail/map presentation only.

**Matching effect:** Prepares reported inputs and explanation preferences only. Existing plan-validation/personal ranking gates remain held.

**Status:** Baseline UI/state/persistence implemented; no independent source/coverage verification.

### T03 · What ZIP code do you live in?

**Exact question:** What ZIP code do you live in?

**Options:** Five-digit home ZIP or Not sure; inline county choice/unknown for ambiguous ZIPs.

**Why:** Plan availability and published prices can depend on the county. A ZIP lookup is a location reference, not proof of residency.

**Fields:** `comparison.scope.zip`, `comparison.scope.county`, `comparison.scope.locationEvidence`.

**Trigger / skip / dedup:** Current app asks this once in the ten-screen route. Alternative reuses a confirmed report supplied earlier, asks only missing fields, and accepts unknown/defer. Do not derive county from a multi-county ZIP. Unique published lookup is derived, not verified residency. Unknown ZIP clears active county evidence.

**Matching effect:** Prepares reported inputs and explanation preferences only. Existing plan-validation/personal ranking gates remain held.

**Status:** Baseline UI/state/persistence implemented; no independent source/coverage verification.

### T04 · When do you need Medicare coverage to start?

**Exact question:** When do you need Medicare coverage to start?

**Options:** Choose a start month; Already on Medicare; Not sure

**Why:** The timing helps organize what to check next. Your requested month does not establish eligibility or an enrollment deadline.

**Fields:** `coverage.requestedStart`, `coverage.requestedStartMonth`.

**Detail controls:** Month and year (YYYY-MM), separately from Already on Medicare.

**Trigger / skip / dedup:** Current app asks this once in the ten-screen route. Alternative reuses a confirmed report supplied earlier, asks only missing fields, and accepts unknown/defer. A requested month uses separately labeled Month and Year selectors with blank new selections, retained saved years, and internal YYYY-MM storage. Unknown saved wording stays intact and can be explicitly kept without interpretation. No exact day is requested. Already on Medicare is a timing report, not a verified enrollment determination. Store the optional date separately from the timing mode.

**Matching effect:** Prepares reported inputs and explanation preferences only. Existing plan-validation/personal ranking gates remain held.

**Status:** Baseline UI/state/persistence implemented; no independent source/coverage verification.

### T05 · What health coverage do you have now?

**Exact question:** What health coverage do you have now?

**Options:** Original Medicare (Parts A and B); Medicare Advantage (Part C); Medicare Supplement / Medigap; Separate prescription drug plan; Current-job coverage; Retiree coverage; COBRA; VA, TRICARE or military coverage; Medicaid; None; Not sure

**Why:** We need to understand what is already in place before considering a change. Your answers describe your coverage; they do not verify its benefits.

**Fields:** `coverage.current`.

**Trigger / skip / dedup:** Current app asks this once in the ten-screen route. Alternative reuses a confirmed report supplied earlier, asks only missing fields, and accepts unknown/defer. Multiple selections are retained until explicitly submitted. Multi-select; None and Not sure are exclusive. Contradictory Original/Advantage reports stay visible for review, never auto-corrected.

**Matching effect:** Prepares reported inputs and explanation preferences only. Existing plan-validation/personal ranking gates remain held.

**Status:** Baseline UI/state/persistence implemented; no independent source/coverage verification.

### T06 · Which doctors or hospitals would you like to keep?

**Exact question:** Which doctors or hospitals would you like to keep?

**Options:** Add doctors or hospitals; None to check; Add later

**Why:** Provider access is an important check before choosing coverage. A name alone does not establish participation or guarantee access.

**Fields:** `needs.providersStatus`, `needs.providers`.

**Detail controls:** All doctor/hospital names, separated by semicolons or newlines.

**Trigger / skip / dedup:** Current app asks this once in the ten-screen route. Alternative reuses a confirmed report supplied earlier, asks only missing fields, and accepts unknown/defer. A name is required only after Add is selected; None to check/Add later require no names. Optional names are sensitive notes.

**Matching effect:** Prepares reported inputs and explanation preferences only. Existing plan-validation/personal ranking gates remain held.

**Status:** Baseline UI/state/persistence implemented; no independent source/coverage verification.

### T07 · What prescriptions do you take?

**Exact question:** What prescriptions do you take?

**Options:** Add prescriptions; None; Add later

**Why:** Drug coverage and costs depend on the exact medicine and plan. Dose and pharmacy details can help later; unknown details can stay open.

**Fields:** `needs.medicinesStatus`, `needs.medications`, `needs.medicationDetails`, `needs.pharmacies`.

**Detail controls:** All medicine names, dose/details and pharmacy notes; each item retained.

**Trigger / skip / dedup:** Current app asks this once in the ten-screen route. Alternative reuses a confirmed report supplied earlier, asks only missing fields, and accepts unknown/defer. A medicine name is required only after Add is selected. Dose and pharmacy may be blank. None/Add later require no list; no match/coverage/cost is inferred.

**Matching effect:** Prepares reported inputs and explanation preferences only. Existing plan-validation/personal ranking gates remain held.

**Status:** Baseline UI/state/persistence implemented; no independent source/coverage verification.

### T08 · Will you need routine care away from home?

**Exact question:** Will you need routine care away from home?

**Options:** Local only; Another state; Outside the US; Not sure

**Why:** Routine care away from home can have different coverage limits from emergency care. Tell us where you expect to need routine care.

**Fields:** `needs.travel`.

**Trigger / skip / dedup:** Current app asks this once in the ten-screen route. Alternative reuses a confirmed report supplied earlier, asks only missing fields, and accepts unknown/defer. Multiple selections are retained until explicitly submitted. Another state and Outside US may coexist. Local only and Not sure are each exclusive. Routine and emergency coverage are distinct.

**Matching effect:** Prepares reported inputs and explanation preferences only. Existing plan-validation/personal ranking gates remain held.

**Status:** Baseline UI/state/persistence implemented; no independent source/coverage verification.

### T09 · How would you prefer to balance monthly payments and costs when you get care?

**Exact question:** How would you prefer to balance monthly payments and costs when you get care?

**Options:** Lower monthly payments; More predictable costs; No preference yet

**Why:** This helps us explain the tradeoffs you care about. It is not enough by itself to choose a coverage route or calculate your total costs.

**Fields:** `needs.costPreference`.

**Trigger / skip / dedup:** Current app asks this once in the ten-screen route. Alternative reuses a confirmed report supplied earlier, asks only missing fields, and accepts unknown/defer. Preference does not select or rank a route. No preference yet is a reported lack of preference, distinct from missing data.

**Matching effect:** Prepares reported inputs and explanation preferences only. Existing plan-validation/personal ranking gates remain held.

**Status:** Baseline UI/state/persistence implemented; no independent source/coverage verification.

### T10 · What matters most when we compare your options?

**Exact question:** What matters most when we compare your options?

**Options:** Doctors and hospitals; Prescriptions; Total cost; Predictable costs; Travel; Something else; Not sure

**Why:** Your priorities should guide the comparison, independently of commissions or other commercial relationships. Choose up to three.

**Fields:** `needs.priorities`, `needs.priorityOther`.

**Trigger / skip / dedup:** Current app asks this once in the ten-screen route. Alternative reuses a confirmed report supplied earlier, asks only missing fields, and accepts unknown/defer. Multiple selections are retained until explicitly submitted. At most three priorities. Not sure is exclusive. Other wording is optional and retained as unresolved if blank.

**Matching effect:** Prepares reported inputs and explanation preferences only. Existing plan-validation/personal ranking gates remain held.

**Status:** Baseline UI/state/persistence implemented; no independent source/coverage verification.

## Conditional registry · RC01–RC30

All conditional questions allow free text, Something else, Not sure and Check later. A disposition closes only the applicable instance; all doctor and medicine instances remain distinct. Existing confirmed facts are reused; partial reports merge. Ambiguity or conflicting changes require confirmation. Dependency gaps stay unresolved. The blocks below preserve exact existing research question/control/schema/trigger/matching wording. Runtime options and fields immediately follow each block to expose any design/runtime differences.

## RC01 · One person and requested check

**Trigger / scope:** A personal comparison is requested and recipient or requested capability is unconfirmed. Reuse a confirmed Ask fact; education-only may bypass. **baseline_by_capability · MVP.**

**Question:** Who is this coverage for?

**Why we ask: We need to keep one person’s details together.**

**Controls:** Me; Someone I help; Research only; Not sure; Something else + text. Every question also supports Not sure, Check later/Defer, Back and Ask. Something else retains brief text and requires confirmed extraction; no invented enum. RC29/RC30 are boundary controls, not automatically queued questions.

**Proposed schema:** `{"subject.role": "self|helper|research|unknown", "request.capabilities": "explicit set"}`. These are design fields, not fields currently accepted by the guest backend.

**Dependencies:** None; integrity guards run before dependent checks.

**Resolution:** Person/context and requested check acknowledged; research may end without personal intake.

**Ambiguity/contradiction:** Caregiver describing own drugs mixed with parent’s coverage: separate profiles, never merge people. Do not demand legal authority just to browse.

**Matching consequence:** Unknown subject holds personalized fit; education/samples remain available.

**Exact runtime question:** Who is this coverage for?

**Exact runtime options:** Me; Someone I help; Research only.

**Runtime fields:** choice only.

**Implemented/source-validation status:** Wired. Ten-question route does not itself supply a role, so it can be a real first gap. Research sources remain unapproved; no verified matching or enrollment capability.

## RC02 · Residence/service area

**Trigger / scope:** Requested availability/network check lacks usable home ZIP/county, spans counties, or moving/seasonal facts conflict with home. **baseline_by_capability · MVP.**

**Question:** Where is your permanent home?

**Why we ask: Plan availability depends on where you live.**

**Controls:** ZIP + county confirmation; Moving: destination and month; Not sure. Every question also supports Not sure, Check later/Defer, Back and Ask. Something else retains brief text and requires confirmed extraction; no invented enum. RC29/RC30 are boundary controls, not automatically queued questions.

**Proposed schema:** `{"scope.homeZip": "5 digits|unknown", "scope.homeCountyFips": "string|unknown", "scope.residence": "permanent|moving|seasonal|unknown"}`. These are design fields, not fields currently accepted by the guest backend.

**Dependencies:** RC01.

**Resolution:** Usable confirmed home scope, or explicit unknown/out-of-area disposition. Do not re-ask an unambiguous confirmed home report solely because it came from Q3.

**Ambiguity/contradiction:** Mailing address, winter address and provider location are not automatically permanent residence. Multi-county ZIP needs county confirmation.

**Matching consequence:** Unknown/outside Collier holds local personalized availability; no false unavailable-plan conclusion.

**Exact runtime question:** Where is your permanent home?

**Exact runtime options:** Add the details I know.

**Runtime fields:** ['zip', 'Home ZIP', 'zip']; ['county', 'Home county and state', 'text']; ['homeStatus', 'Permanent-home or moving/seasonal clarification', 'text'].

**Implemented/source-validation status:** Partial seeding/merging implemented; asks only missing existing fields. No residence verification. Research sources remain unapproved; no verified matching or enrollment capability.

## RC03 · Benefit year and intended start

**Trigger / scope:** Requested benefit year/start is unknown, mismatches source year, or already-on-Medicare answer supplied no comparison year. **baseline_by_capability · MVP.**

**Question:** Which year should we compare?

**Why we ask: Plan benefits and prices can change each year.**

**Controls:** 2026; 2027; Another year + year; Not sure. Every question also supports Not sure, Check later/Defer, Back and Ask. Something else retains brief text and requires confirmed extraction; no invented enum. RC29/RC30 are boundary controls, not automatically queued questions.

**Proposed schema:** `{"scope.benefitYear": "YYYY|unknown", "timing.requestedStart": "YYYY-MM|unknown"}`. These are design fields, not fields currently accepted by the guest backend.

**Dependencies:** RC01.

**Resolution:** Explicit year, reusing confirmed Q4 requested month/year where it determines the requested comparison.

**Ambiguity/contradiction:** Today’s year, future plan year and current enrollment year are distinct. Unsupported year is not an answer error.

**Matching consequence:** Mismatched/unsupported year holds current cost/availability claims, not general education.

**Exact runtime question:** Which year should we compare?

**Exact runtime options:** 2026; 2027; Another year.

**Runtime fields:** ['year', 'Other benefit year', 'year'].

**Implemented/source-validation status:** Wired. Requested date never becomes an actual A/B start date. Research sources remain unapproved; no verified matching or enrollment capability.

## RC04 · Actual A/B enrollment

**Trigger / scope:** Personal health/drug candidates requested and active/pending Part A/Part B status is not independently represented; Q4 Already on Medicare is insufficient. **baseline_by_capability · MVP.**

**Question:** Which Medicare parts do you have now?

**Why we ask: Different plans require different Medicare parts.**

**Controls:** A and B; A only; B only; Neither; Applied; waiting; Not sure. Every question also supports Not sure, Check later/Defer, Back and Ask. Something else retains brief text and requires confirmed extraction; no invented enum. RC29/RC30 are boundary controls, not automatically queued questions.

**Proposed schema:** `{"enrollment.partA.status": "active|pending|not_active|unknown", "enrollment.partB.status": "active|pending|not_active|unknown"}`. These are design fields, not fields currently accepted by the guest backend.

**Dependencies:** RC01.

**Resolution:** Both parts have explicit reported/unknown statuses; pending stays pending.

**Ambiguity/contradiction:** An Advantage member still has A/B. Do not call A+B plus Advantage contradictory. Do not infer premium-free A or eligibility from age.

**Matching consequence:** Unknown A/B holds eligible-to-join claims; MA requires both, standalone D A or B. Browse only with explicit assumptions.

**Exact runtime question:** Which Medicare parts do you have now?

**Exact runtime options:** A and B; A only; B only; Neither; Applied; waiting.

**Runtime fields:** choice only.

**Implemented/source-validation status:** Wired for reported inputs only; Advantage alone does not assert actual enrollment. Research sources remain unapproved; no verified matching or enrollment capability.

## RC05 · Actual effective dates

**Trigger / scope:** Timing/Medigap/change review needs actual A/B dates and they are missing or different from requested start. **baseline_by_capability · MVP.**

**Question:** When did Part B start?

**Why we ask: This can affect your enrollment and Medigap options.**

**Controls:** Month/year selector; Not started yet; Not sure. Every question also supports Not sure, Check later/Defer, Back and Ask. Something else retains brief text and requires confirmed extraction; no invented enum. RC29/RC30 are boundary controls, not automatically queued questions.

**Proposed schema:** `{"enrollment.partB.effective": "date with precision|pending|unknown", "enrollment.partA.effective": "same, asked separately only if needed"}`. These are design fields, not fields currently accepted by the guest backend.

**Dependencies:** RC04.

**Resolution:** Relevant dates recorded with precision and provenance, or timing explicitly held.

**Ambiguity/contradiction:** One date does not establish both parts. Retroactive A differs from B; requested start is never substituted.

**Matching consequence:** Missing dates hold affected timing/GI calculations, not already sourced benefit browsing.

**Exact runtime question:** When did Part B start?

**Exact runtime options:** Add the details I know.

**Runtime fields:** ['month', 'Part B start month, if known', 'month'].

**Implemented/source-validation status:** Part B input wired. A material Part A timing selector/calculation is not implemented; requires reviewed timing policy, not an invented rule. Research sources remain unapproved; no verified matching or enrollment capability.

## RC06 · Age/eligibility basis

**Trigger / scope:** Timing, premium eligibility or Medigap rights need age/basis that existing confirmed enrollment does not resolve; not a universal diagnosis screen. **conditional · MVP.**

**Question:** How did you first qualify for Medicare?

**Why we ask: Some enrollment rules depend on how you qualified.**

**Controls:** Turning 65; Disability before 65; Kidney failure / ESRD; ALS; Another reason; Not sure. Every question also supports Not sure, Check later/Defer, Back and Ask. Something else retains brief text and requires confirmed extraction; no invented enum. RC29/RC30 are boundary controls, not automatically queued questions.

**Proposed schema:** `{"eligibility.basis": "age|disability|ESRD|ALS|other|unknown", "eligibility.ageBand": "under65|65plus|unknown", "eligibility.birthMonthYear": "optional only when timing needs it", "eligibility.firstDayBirthday": "yes|no|unknown when timing material"}`. These are design fields, not fields currently accepted by the guest backend.

**Dependencies:** RC04.

**Resolution:** Relevant basis/age or explicit unknown; ask birthday month/year only if calculation requires it.

**Ambiguity/contradiction:** Disability benefits are not always active Medicare. ESRD/ALS timing differs. No full birth date or citizenship documents for ordinary research.

**Matching consequence:** Unknown holds basis-dependent timing/rights/quotes; no automatic ineligibility or age-based recommendation.

**Exact runtime question:** How did you first qualify, or expect to qualify, for Medicare?

**Exact runtime options:** Age 65 or older; Disability before 65; Kidney failure / ESRD; ALS; Another reason.

**Runtime fields:** ['ageBand', 'Current age range, if known', 'ageBand'].

**Implemented/source-validation status:** Wired. No universal age/basis screen or eligibility decision. Research sources remain unapproved; no verified matching or enrollment capability.

## RC07 · Current arrangement vs planned change

**Trigger / scope:** Current medical arrangement has incompatible same-period reports or user wants to leave MA/Medigap without a clear current-versus-future distinction. **conditional · MVP.**

**Question:** How do you get your A and B benefits now?

**Why we ask: We need to separate current coverage from a possible change.**

**Controls:** Original Medicare; Medicare Advantage; A change is pending; Not sure. Every question also supports Not sure, Check later/Defer, Back and Ask. Something else retains brief text and requires confirmed extraction; no invented enum. RC29/RC30 are boundary controls, not automatically queued questions.

**Proposed schema:** `{"coverage.currentArrangement": "original|advantage|pending_change|unknown", "coverage.planEffective": "dated report|unknown", "coverage.changeIntent": "keep|explore|change|unknown"}`. These are design fields, not fields currently accepted by the guest backend.

**Dependencies:** RC04.

**Resolution:** Current arrangement and any future change separated; contradictory reports preserved with a resolution link.

**Ambiguity/contradiction:** Both Medicare card and MA card can be normal. A reported Medigap policy with MA may be unused/suspended; do not accuse or silently delete it.

**Matching consequence:** Unresolved arrangement holds safe change-path conclusions and duplicate-coverage assumptions.

**Exact runtime question:** How do you get your A and B benefits now?

**Exact runtime options:** Original Medicare; Medicare Advantage; A change is pending.

**Runtime fields:** choice only.

**Implemented/source-validation status:** Wired. A/B plus Advantage is not inherently a conflict. Research sources remain unapproved; no verified matching or enrollment capability.

## RC08 · Enrollment event/window

**Trigger / scope:** User requests a change/start outside an established reviewed window, or reports move, loss, plan termination, institutional stay, disaster or other potential event. **conditional · MVP.**

**Question:** What changed about your coverage?

**Why we ask: This can affect when you can enroll.**

**Controls:** Losing coverage; Moving; Plan ending/changing service area; Medicaid/Extra Help change; Another event + text; Nothing changed; Not sure. Every question also supports Not sure, Check later/Defer, Back and Ask. Something else retains brief text and requires confirmed extraction; no invented enum. RC29/RC30 are boundary controls, not automatically queued questions.

**Proposed schema:** `{"timing.event": "approved enum|other|unknown", "timing.eventDate": "date+precision|unknown", "timing.noticeDate": "date+precision|unknown if relevant"}`. These are design fields, not fields currently accepted by the guest backend.

**Dependencies:** RC03, RC04, RC07.

**Resolution:** Applicable event details are available for source-backed review, or window remains unknown.

**Ambiguity/contradiction:** Part B, MA/PDP and Medigap windows are separate. A doctor leaving a network is not automatically any generic SEP. Unknown notice date is not fabricated.

**Matching consequence:** Unknown holds enrollment-action readiness only; scoped browsing may proceed.

**Exact runtime question:** What changed about your coverage?

**Exact runtime options:** Losing coverage; Moving; Plan ending or changing service area; Medicaid or Extra Help changed; Another event; Nothing changed.

**Runtime fields:** ['eventDate', 'Date of the change, if known', 'date'].

**Implemented/source-validation status:** Wired. No generic event screen for every review goal. Research sources remain unapproved; no verified matching or enrollment capability.

## RC09 · Current employment vs continuation

**Trigger / scope:** Q5 employer/retiree/COBRA or free text indicates job-related insurance, but source of coverage/current-work relationship unclear. **conditional · MVP.**

**Question:** Is this coverage from someone who is still working?

**Why we ask: Current work can affect your Medicare sign-up window.**

**Controls:** My current job; Spouse’s current job; Family member’s current job; Retiree coverage; COBRA; Other/Not sure. Every question also supports Not sure, Check later/Defer, Back and Ask. Something else retains brief text and requires confirmed extraction; no invented enum. RC29/RC30 are boundary controls, not automatically queued questions.

**Proposed schema:** `{"work.coverageKind": "self_current|spouse_current|family_current|retiree|COBRA|other|unknown"}`. These are design fields, not fields currently accepted by the guest backend.

**Dependencies:** RC07.

**Resolution:** Coverage kind/current work clarified or explicitly unresolved.

**Ambiguity/contradiction:** An employer name does not mean active-employment coverage; a stipend/individual policy may differ. Multiple jobs/plans remain separate.

**Matching consequence:** Unknown holds delay/payer-order advice; not a reason to suppress noncommercial plan options.

**Exact runtime question:** Is this coverage from someone who is still working?

**Exact runtime options:** My current job; Spouse’s current job; Family member’s current job; Retiree coverage; COBRA.

**Runtime fields:** choice only.

**Implemented/source-validation status:** Wired on consequential work/timing/change paths. Research sources remain unapproved; no verified matching or enrollment capability.

## RC10 · Relevant employer size

**Trigger / scope:** Current group coverage plus payer-order question; age/basis known. Do not run age threshold for ESRD. **conditional · MVP.**

**Question:** Does the employer have 20 or more employees?

**Why we ask: Employer size can change which coverage pays first.**

**Controls:** Yes; No; Not sure. Every question also supports Not sure, Check later/Defer, Back and Ask. Something else retains brief text and requires confirmed extraction; no invented enum. RC29/RC30 are boundary controls, not automatically queued questions.

**Proposed schema:** `{"work.sizeBand": "under20|20to99|100plus|unknown", "work.multiEmployer": "yes|no|unknown"}`. These are design fields, not fields currently accepted by the guest backend.

**Dependencies:** RC06, RC09.

**Resolution:** Age-65 case uses 20 threshold; under-65 disability variant asks “100 or more employees?”; uncertain multi-employer facts remain held.

**Ambiguity/contradiction:** Do not use 20 universally; do not apply either shortcut to ESRD. Family-member coverage under disability needs exact review.

**Matching consequence:** Unresolved holds payer-order/delay conclusions; plan benefit comparison still possible with warnings.

**Exact runtime question:** Does the employer have 20 or more employees?

**Exact runtime options:** Yes; No.

**Runtime fields:** choice only.

**Implemented/source-validation status:** Wired 20/100 question variants; no ESRD shortcut or payer determination. Research sources remain unapproved; no verified matching or enrollment capability.

## RC11 · Separate loss/job dates

**Trigger / scope:** Coverage/job ending or ended, COBRA/retiree transition, or prospective change needs loss chronology. **conditional · MVP.**

**Question:** When did the job end?

**Why we ask: Different end dates can change your sign-up window.**

**Controls:** Date selector with unknown parts allowed; Still working; Not sure. Every question also supports Not sure, Check later/Defer, Back and Ask. Something else retains brief text and requires confirmed extraction; no invented enum. RC29/RC30 are boundary controls, not automatically queued questions.

**Proposed schema:** `{"work.employmentEnd": "date+precision|still_working|unknown", "work.activeCoverageEnd": "separate date+precision|ongoing|unknown", "work.continuationEnd": "separate if relevant"}`. These are design fields, not fields currently accepted by the guest backend.

**Dependencies:** RC09.

**Resolution:** Ask approved child “When does the job-based health coverage end?” only if missing; save dates independently.

**Ambiguity/contradiction:** Do not substitute retirement, COBRA expiry, notice date or requested start for active group coverage loss. Ranges crossing a deadline stay uncertain.

**Matching consequence:** Missing dates hold transition/deadline advice; explain which exact check remains open.

**Exact runtime question:** When did the job or coverage end?

**Exact runtime options:** Add the end dates I know; Still working.

**Runtime fields:** ['jobEnd', 'Job end date, if known', 'date']; ['coverageEnd', 'Coverage end date, if known', 'date'].

**Implemented/source-validation status:** Wired; partial dates merge and unknowns remain unresolved. Research sources remain unapproved; no verified matching or enrollment capability.

## RC12 · Creditable drug coverage/gap

**Trigger / scope:** Part D is absent/ending/unknown and employer/retiree/military/other drug coverage might exist, or user proposes no drug coverage. **conditional · MVP.**

**Question:** Does your plan say its drug coverage is creditable?

**Why we ask: A gap in qualifying drug coverage can affect later costs.**

**Controls:** Yes, according to its notice; No; I have no drug coverage; Not sure. Every question also supports Not sure, Check later/Defer, Back and Ask. Something else retains brief text and requires confirmed extraction; no invented enum. RC29/RC30 are boundary controls, not automatically queued questions.

**Proposed schema:** `{"drugCoverage.creditableReport": "yes|no|none|unknown", "drugCoverage.lastCoveredDay": "date+precision|ongoing|unknown"}`. These are design fields, not fields currently accepted by the guest backend.

**Dependencies:** RC07, RC09.

**Resolution:** Notice status and relevant end date recorded or unresolved; no penalty amount invented.

**Ambiguity/contradiction:** No current prescriptions does not mean no need to consider D. The 63-day issue is not an MA/PDP election deadline or the eight-month Part B clock.

**Matching consequence:** Unknown holds penalty/transition conclusions; no blanket no-D recommendation.

**Exact runtime question:** Do you have a written notice saying your drug coverage counts as creditable (as good as Medicare’s standard coverage), and has there been a gap?

**Exact runtime options:** Yes, according to its notice; No; I have no drug coverage.

**Runtime fields:** ['gap', 'Drug coverage gap, if any', 'text'].

**Implemented/source-validation status:** Wired across applicable coverage categories; missing-gap follow-up preserves a known notice. No penalty calculation. Research sources remain unapproved; no verified matching or enrollment capability.

## RC13 · Retiree/family benefit consequences

**Trigger / scope:** Employer/union/retiree coverage exists and user considers joining outside MA/PDP or dropping group coverage. **conditional · MVP.**

**Question:** Could a change affect anyone else’s coverage?

**Why we ask: Some changes can affect family or retiree benefits.**

**Controls:** Administrator says yes; Administrator says no; I have not checked; Not sure. Every question also supports Not sure, Check later/Defer, Back and Ask. Something else retains brief text and requires confirmed extraction; no invented enum. RC29/RC30 are boundary controls, not automatically queued questions.

**Proposed schema:** `{"coordination.familyRisk": "yes|no|unchecked|unknown", "coordination.adminChecked": "reported date/source|unknown"}`. These are design fields, not fields currently accepted by the guest backend.

**Dependencies:** RC09.

**Resolution:** Administrator report recorded; unchecked remains a specific action item.

**Ambiguity/contradiction:** Joining an outside plan can have consequences beyond the beneficiary. Do not assume coverage can be restored.

**Matching consequence:** Unconfirmed holds recommended change/action; general comparison can remain available.

**Exact runtime question:** Could a change affect anyone else’s coverage?

**Exact runtime options:** Administrator says yes; Administrator says no; I have not checked.

**Runtime fields:** choice only.

**Implemented/source-validation status:** Wired as a reported administrator check, not verified preservation. Research sources remain unapproved; no verified matching or enrollment capability.

## RC14 · HSA timing

**Trigger / scope:** User reports current-work coverage, Medicare deferral/retroactive A or specifically mentions HSA contributions. **conditional · MVP.**

**Question:** Are you or your employer adding money to an HSA?

**Why we ask: Medicare start dates can affect HSA contributions.**

**Controls:** Yes; No; Not sure. Every question also supports Not sure, Check later/Defer, Back and Ask. Something else retains brief text and requires confirmed extraction; no invented enum. RC29/RC30 are boundary controls, not automatically queued questions.

**Proposed schema:** `{"work.hsaContributions": "yes|no|unknown"}`. These are design fields, not fields currently accepted by the guest backend.

**Dependencies:** RC05, RC09.

**Resolution:** No ends the trigger; yes/unknown creates review task, never an automated tax instruction.

**Ambiguity/contradiction:** An HSA balance differs from current contributions. Do not request balance/account number or equate retirement date with Part A effective date.

**Matching consequence:** Holds HSA/tax timing advice; not all plan comparisons.

**Exact runtime question:** Are you or your employer adding money to an HSA?

**Exact runtime options:** Yes; No.

**Runtime fields:** choice only.

**Implemented/source-validation status:** Wired; no balance/account intake or tax determination. Research sources remain unapproved; no verified matching or enrollment capability.

## RC15 · Florida Medigap purchase window

**Trigger / scope:** Original+Medigap purchase/replacement path requested; age, basis, Part B start or qualifying group-loss dates are missing or not reviewed. **conditional · MVP.**

**Question:** When did your Part B coverage begin?

**Why we ask: This can affect your Medigap purchase rights.**

**Controls:** Month/year selector; Not sure. Every question also supports Not sure, Check later/Defer, Back and Ask. Something else retains brief text and requires confirmed extraction; no invented enum. RC29/RC30 are boundary controls, not automatically queued questions.

**Proposed schema:** `{"medigap.partBStart": "reference enrollment date, no duplicate fact", "medigap.rightsReview": "pending|reviewed; never LLM-qualified"}`. These are design fields, not fields currently accepted by the guest backend.

**Dependencies:** RC02, RC05, RC06, RC11.

**Resolution:** Reuse dates already confirmed; evaluate federal and Florida candidates separately. Resolution is facts sufficient for expert review, not guaranteed issue confirmed.

**Ambiguity/contradiction:** Florida six-month and qualifying group-termination two-month provisions differ from federal event-specific rights. Do not promise every policy/price or apply Florida elsewhere.

**Matching consequence:** Unreviewed rights hold issueability/underwriting-free/quote eligibility claims; public Medigap benefit explanations remain possible.

**Exact runtime question:** For the Medigap option you want to explore, what coverage change or notice should we check?

**Exact runtime options:** Relevant change or notice; No change or notice known.

**Runtime fields:** ['event', 'Relevant change or notice', 'text'].

**Implemented/source-validation status:** Wired; reuses RC05 date, no duplicate Part B question or guarantee. Research sources remain unapproved; no verified matching or enrollment capability.

## RC16 · Trial/guaranteed-issue history

**Trigger / scope:** Current/recent MA plus interest in Original+Medigap, lost supplement, plan termination/move or alleged insurer misconduct. **conditional · MVP.**

**Question:** Was this your first Medicare Advantage plan?

**Why we ask: Your coverage history may affect Medigap rights.**

**Controls:** Yes; No; Not sure. Every question also supports Not sure, Check later/Defer, Back and Ask. Something else retains brief text and requires confirmed extraction; no invented enum. RC29/RC30 are boundary controls, not automatically queued questions.

**Proposed schema:** `{"medigap.firstMA": "yes|no|unknown", "medigap.maJoinDate": "date+precision|unknown", "medigap.hadPriorPolicy": "yes|no|unknown", "medigap.eventEvidence": "notice type/date|unknown"}`. These are design fields, not fields currently accepted by the guest backend.

**Dependencies:** RC07, RC08, RC15.

**Resolution:** Only missing approved child questions asked: “When did it start?” and “Did you have Medigap before it?” Events reach specialist review.

**Ambiguity/contradiction:** First MA at initial Medicare eligibility and dropping Medigap to try MA are distinct trial patterns; plan letters/availability differ. Never convert within-12-month report alone to guaranteed rights.

**Matching consequence:** Holds guaranteed-issue/transition confidence; does not hide Original/MA alternatives.

**Exact runtime question:** Was this your first Medicare Advantage plan, when did it start, and did you have Medigap before?

**Exact runtime options:** Yes; No.

**Runtime fields:** ['start', 'Advantage start date', 'date']; ['priorMedigap', 'Prior Medigap, if any', 'text'].

**Implemented/source-validation status:** Wired; history fields stay distinct, no trial-right determination. Research sources remain unapproved; no verified matching or enrollment capability.

## RC17 · Existing Medigap replacement

**Trigger / scope:** User already has Medigap and wants another supplement/carrier or is considering dropping it. **conditional · MVP.**

**Question:** Are you replacing an existing Medigap policy?

**Why we ask: You may not have the same rights to buy it again.**

**Controls:** Yes; No, keeping it; Not sure. Every question also supports Not sure, Check later/Defer, Back and Ask. Something else retains brief text and requires confirmed extraction; no invented enum. RC29/RC30 are boundary controls, not automatically queued questions.

**Proposed schema:** `{"medigap.replacementIntent": "replace|keep|unknown", "medigap.currentPolicy": "letter/carrier/version report|unknown"}`. These are design fields, not fields currently accepted by the guest backend.

**Dependencies:** RC07, RC15.

**Resolution:** Keep means no replacement intake; replace/unknown retains current coverage and review task.

**Ambiguity/contradiction:** Annual MA/PDP open enrollment is not universal Medigap open enrollment. Do not demand diagnosis/underwriting history in this readiness chat.

**Matching consequence:** Holds accepted/purchasable replacement claim and cancellation steps, not standardized-benefit browsing.

**Exact runtime question:** Are you replacing an existing Medigap policy?

**Exact runtime options:** Yes, replacing it; No, keeping it.

**Runtime fields:** choice only.

**Implemented/source-validation status:** Wired; no cancellation/application action. Research sources remain unapproved; no verified matching or enrollment capability.

## RC18 · Assistance status without financial intake

**Trigger / scope:** Subsidy-adjusted costs, a reported Medicaid program, affordability concern or explicit help request makes program status consequential. **conditional · MVP.**

**Question:** Do you get help with Medicare costs now?

**Why we ask: Assistance can change what you pay.**

**Controls:** Medicaid; Extra Help; Help paying Part B; SSI; None known; Not sure; Prefer not to say. Every question also supports Not sure, Check later/Defer, Back and Ask. Something else retains brief text and requires confirmed extraction; no invented enum. RC29/RC30 are boundary controls, not automatically queued questions.

**Proposed schema:** `{"assistance.programReports": "set of enums|unknown|declined", "assistance.effectiveYear": "YYYY|unknown"}`. These are design fields, not fields currently accepted by the guest backend.

**Dependencies:** RC01, RC03.

**Resolution:** Current program reports/unknown/declined recorded; offer official application support, not a local eligibility decision.

**Ambiguity/contradiction:** Medicaid, QMB/MSP, Extra Help and SSI are distinct. Program amount/year can change; no bank, tax-return or account collection here.

**Matching consequence:** Unknown holds personalized subsidy-adjusted costs/SNP eligibility, not unsubsidized labeled scenarios.

**Exact runtime question:** Do you get help with Medicare costs now? You can name more than one program.

**Exact runtime options:** Medicaid; Extra Help; Help paying Part B; SSI; None known; Prefer not to say.

**Runtime fields:** choice only.

**Implemented/source-validation status:** Wired. Unknown is not ineligibility. Research sources remain unapproved; no verified matching or enrollment capability.

## RC19 · SNP-specific qualification

**Trigger / scope:** User asks about an SNP or volunteers Medicaid/qualifying institutional/chronic circumstances and a supported candidate actually requires them. **conditional · MVP flags/referral; detailed SNP matching future.**

**Question:** Has anyone confirmed you qualify for this type of special-needs plan?

**Why we ask: These plans have additional enrollment requirements.**

**Controls:** Yes, current notice/plan confirmation; No; Not sure; I do not want to explore these plans. Every question also supports Not sure, Check later/Defer, Back and Ask. Something else retains brief text and requires confirmed extraction; no invented enum. RC29/RC30 are boundary controls, not automatically queued questions.

**Proposed schema:** `{"snp.reportedCategory": "dual|chronic|institutional|unknown", "snp.verification": "pending|verified evidence ref only"}`. These are design fields, not fields currently accepted by the guest backend.

**Dependencies:** RC02, RC04, RC18.

**Resolution:** Category and evidence routed to plan/state review; decline closes this optional exploration without erasing known assistance.

**Ambiguity/contradiction:** Extra Help alone is not full Medicaid or proof of D-SNP alignment; a diagnosis mention is not verified C-SNP eligibility. No exhaustive diagnosis questionnaire.

**Matching consequence:** Only SNP eligibility/fit held; other available paths not suppressed.

**Exact runtime question:** For the Special Needs Plan type you want to explore, what exact qualifying program or plan confirmation do you have?

**Exact runtime options:** Program or plan confirmation; No confirmation; Do not explore this type.

**Runtime fields:** ['qualification', 'Specific qualifying program or plan confirmation', 'text'].

**Implemented/source-validation status:** Definition/activation wired; actual qualification detail is required for a `details` report. No independent qualification verification. Research sources remain unapproved; no verified matching or enrollment capability.

## RC20 · Seasonal/routine travel

**Trigger / scope:** Q8 another-state/outside-US/unknown or moving/seasonal facts make care locations material to requested provider/travel fit. **conditional · MVP.**

**Question:** Where will you need routine care away from home?

**Why we ask: Routine care and emergency care can have different coverage.**

**Controls:** Another U.S. state + location; Outside the U.S. + optional country; Emergency travel cover only; Not sure. Every question also supports Not sure, Check later/Defer, Back and Ask. Something else retains brief text and requires confirmed extraction; no invented enum. RC29/RC30 are boundary controls, not automatically queued questions.

**Proposed schema:** `{"travel.routineLocations": "bounded public-location list", "travel.need": "routine|emergency|both|unknown"}`. These are design fields, not fields currently accepted by the guest backend.

**Dependencies:** RC02.

**Resolution:** Routine/emergency need and locations clarified or travel-fit limitation retained.

**Ambiguity/contradiction:** Seasonal stay does not automatically change permanent home. A PPO label or foreign emergency benefit does not promise routine access.

**Matching consequence:** Unknown holds travel-fit claims only; no automated Original-over-Advantage preference.

**Exact runtime question:** Where will you need routine care away from home?

**Exact runtime options:** Another U.S. state; Outside the U.S.; Emergency travel cover only.

**Runtime fields:** ['location', 'State or country, if known', 'text'].

**Implemented/source-validation status:** Wired. Reported travel is not a network/benefit guarantee. Research sources remain unapproved; no verified matching or enrollment capability.

## RC21 · Exact provider identity/location

**Trigger / scope:** Provider-fit requested and Q6 names are unresolved, ambiguous, location-free, or source/network result unavailable. **conditional · MVP.**

**Question:** Which location do you use for this doctor?

**Why we ask: The office location can affect the network check.**

**Controls:** Office/practice + city; Choose a verified identity candidate; Add later; No longer needed. Every question also supports Not sure, Check later/Defer, Back and Ask. Something else retains brief text and requires confirmed extraction; no invented enum. RC29/RC30 are boundary controls, not automatically queued questions.

**Proposed schema:** `{"providers.entities": "id,name,public practice/location,priority,report status", "providers.networkChecks": "plan/year/as-of/evidence, separate"}`. These are design fields, not fields currently accepted by the guest backend.

**Dependencies:** RC02, RC03.

**Resolution:** User confirms the exact provider/location; identity resolution remains separate from network verification.

**Ambiguity/contradiction:** Do not choose among duplicate names by LLM confidence. Hospital/facility and doctor may need distinct checks; Medicare acceptance is not MA participation.

**Matching consequence:** Missing identity holds fit for that provider. Missing network source is a system limitation, not a negative score or another user question.

**Exact runtime question:** What exact office and location should we use for each doctor or hospital?

**Exact runtime options:** Add practice and location; No longer needed.

**Runtime fields:** ['entity', 'Listed doctor reference', 'text']; ['practice', 'Doctor / hospital and practice', 'text']; ['city', 'Office city and state', 'text'].

**Implemented/source-validation status:** Entity queue wired; raw names are retained without treating them as exact offices. External identity/network resolution held. Research sources remain unapproved; no verified matching or enrollment capability.

## RC22 · Exact prescription identity

**Trigger / scope:** Drug-fit/cost requested and medication string lacks a unique ingredient/brand, strength or form; preserve original wording. **conditional · MVP.**

**Question:** Which version of this prescription do you take?

**Why we ask: Strength and form can change the coverage check.**

**Controls:** Name/strength/form fields or verified candidates; Not sure; Add later; No longer taking. Every question also supports Not sure, Check later/Defer, Back and Ask. Something else retains brief text and requires confirmed extraction; no invented enum. RC29/RC30 are boundary controls, not automatically queued questions.

**Proposed schema:** `{"medications.entities": "id,originalText,ingredient/brand,strength,form,RxNorm candidate/user confirmation", "medications.active": "yes|no|unknown"}`. These are design fields, not fields currently accepted by the guest backend.

**Dependencies:** RC03.

**Resolution:** Confirmed identity tuple or explicit unresolved entity; one prompt per grouped missing tuple, not every field as another page.

**Ambiguity/contradiction:** Similar names, extended-release vs immediate-release, salt/route and brand alternatives must not be silently substituted. Do not recommend medication changes.

**Matching consequence:** Unknown holds that drug’s coverage/price, not an inferred uncovered verdict or all general plan information.

**Exact runtime question:** What exact name, strength, form, and brand or generic preference should we use for each medicine?

**Exact runtime options:** Add exact name, strength and form; No longer taking.

**Runtime fields:** ['entity', 'Listed medicine reference', 'text']; ['name', 'Prescription name', 'text']; ['strength', 'Strength', 'text']; ['form', 'Form, such as tablet or inhaler', 'text']; ['brand', 'Brand or generic preference, including no preference', 'text'].

**Implemented/source-validation status:** Partial-report validation and literal supplied-detail reuse implemented. No silent substitution or Rx identity/coverage claim. Research sources remain unapproved; no verified matching or enrollment capability.

## RC23 · Supply and pharmacy

**Trigger / scope:** A drug-cost check is requested and days supply/quantity/fill channel or exact pharmacy is missing. **conditional · MVP.**

**Question:** How do you usually fill this prescription?

**Why we ask: Supply and pharmacy can change the price.**

**Controls:** Quantity + days supply; pharmacy/location; Mail order; Not sure; Add later. Every question also supports Not sure, Check later/Defer, Back and Ask. Something else retains brief text and requires confirmed extraction; no invented enum. RC29/RC30 are boundary controls, not automatically queued questions.

**Proposed schema:** `{"medications.fill": "quantity,unit,daysSupply|unknown", "pharmacies.preferred": "exact public identity/location|unknown", "pharmacies.channel": "retail|mail|specialty|unknown"}`. These are design fields, not fields currently accepted by the guest backend.

**Dependencies:** RC22.

**Resolution:** Required pricing inputs complete or the cost dimension explicitly withheld.

**Ambiguity/contradiction:** Dose instructions and dispensed quantity differ. Preferred vs standard network, specialty channels and travel pharmacies need evidence, not guesses.

**Matching consequence:** Missing inputs hold personal drug estimate only; a flat copay or premium must not stand in for total cost.

**Exact runtime question:** For each medicine, what quantity, days supply, exact pharmacy and retail or mail order should we use?

**Exact runtime options:** Add supply and pharmacy; Mail order.

**Runtime fields:** ['entity', 'Listed medicine reference', 'text']; ['quantity', 'Quantity', 'text']; ['daysSupply', 'Days supply', 'text']; ['pharmacy', 'Exact pharmacy and location', 'text']; ['channel', 'Retail or mail order', 'text']; ['supply', 'Earlier reported supply wording', 'text'].

**Implemented/source-validation status:** Wired per medicine; missing pricing adapters remain a system hold. Research sources remain unapproved; no verified matching or enrollment capability.

## RC24 · Restrictions and Part B/D boundary

**Trigger / scope:** Validated source flags PA/ST/quantity restrictions, administration setting is ambiguous, or user reports a current exception/coverage problem. **conditional · MVP.**

**Question:** Is this given at a clinic or filled at a pharmacy?

**Why we ask: Some medicines use different Medicare coverage rules.**

**Controls:** At a clinic; At a pharmacy; Both/Not sure. Every question also supports Not sure, Check later/Defer, Back and Ask. Something else retains brief text and requires confirmed extraction; no invented enum. RC29/RC30 are boundary controls, not automatically queued questions.

**Proposed schema:** `{"medications.setting": "clinic|pharmacy|both|unknown", "medications.restrictions": "source-derived, not user-guessed", "medications.currentApprovalReport": "yes|no|unknown if material"}`. These are design fields, not fields currently accepted by the guest backend.

**Dependencies:** RC22, RC23.

**Resolution:** Setting/reported problem preserved; restriction approval remains separate pending plan/prescriber confirmation.

**Ambiguity/contradiction:** An old authorization does not establish approval under a new plan. Do not ask users to diagnose which Medicare part pays or waive requirements.

**Matching consequence:** Restricted coverage displayed as conditional; unsupported Part-B drug costing withheld instead of marked not covered.

**Exact runtime question:** Is this given at a clinic or filled at a pharmacy?

**Exact runtime options:** At a clinic; At a pharmacy; Both / Not sure.

**Runtime fields:** choice only.

**Implemented/source-validation status:** Basic setting report wired. Source-derived restrictions and per-drug benefit adjudication are unavailable. Research sources remain unapproved; no verified matching or enrollment capability.

## RC25 · Affordability vs preference

**Trigger / scope:** Cost priority or numeric budget request is material; Q9 cost preference alone does not establish affordability or total annual spending. **conditional · MVP.**

**Question:** Is there a monthly amount you want to stay under?

**Why we ask: A low plan premium is not the whole cost.**

**Controls:** Optional amount/range + what it includes; No fixed limit; Not sure; Prefer not to say. Every question also supports Not sure, Check later/Defer, Back and Ask. Something else retains brief text and requires confirmed extraction; no invented enum. RC29/RC30 are boundary controls, not automatically queued questions.

**Proposed schema:** `{"cost.monthlyLimit": "number/range|unknown|declined", "cost.limitBasis": "all recurring premiums|plan only|unknown", "cost.utilizationAssumptions": "explicit scenario, not inferred"}`. These are design fields, not fields currently accepted by the guest backend.

**Dependencies:** RC03, RC18.

**Resolution:** Budget basis acknowledged or unknown; do not force financial disclosure.

**Ambiguity/contradiction:** Include/exclude Part B, Medigap, drug/medical use and possible income adjustments explicitly. No income/tax documents here; unknown medical use prevents a guaranteed total.

**Matching consequence:** Unknown budget limits affordability assessment only; absent source/care-use assumptions holds personalized total/ranking, not all browsing.

**Exact runtime question:** Is there a monthly amount you want to stay under?

**Exact runtime options:** Add an optional budget; No fixed limit; Prefer not to say.

**Runtime fields:** ['amount', 'Monthly amount or range, if you want', 'text']; ['includes', 'What should that amount include?', 'text'].

**Implemented/source-validation status:** Activation and missing amount/basis subfields wired. Decline/no-limit closes the instance. No personalized total. Research sources remain unapproved; no verified matching or enrollment capability.

## RC26 · Military/veterans coordination

**Trigger / scope:** Q5 military category or free text indicates VA, TRICARE, CHAMPVA or another federal program without exact program context. **conditional · MVP.**

**Question:** Which military or veterans’ coverage do you have?

**Why we ask: These programs work with Medicare in different ways.**

**Controls:** VA health care; TRICARE For Life; Other TRICARE; CHAMPVA; Another program; Not sure. Every question also supports Not sure, Check later/Defer, Back and Ask. Something else retains brief text and requires confirmed extraction; no invented enum. RC29/RC30 are boundary controls, not automatically queued questions.

**Proposed schema:** `{"coordination.federalProgram": "enum|unknown", "coordination.offSystemCare": "reported need|unknown"}`. These are design fields, not fields currently accepted by the guest backend.

**Dependencies:** RC04, RC12.

**Resolution:** Program classified for correct official referral; unresolved stays unknown.

**Ambiguity/contradiction:** VA is not TRICARE. Do not universally advise joining/dropping D, dropping B or adding Medigap; family consequences may matter.

**Matching consequence:** Unresolved holds coordination and recommended change conclusions, not neutral education.

**Exact runtime question:** Which military or veterans’ coverage do you have?

**Exact runtime options:** VA health care; TRICARE For Life; Other TRICARE; CHAMPVA; Another program.

**Runtime fields:** choice only.

**Implemented/source-validation status:** Report preparation wired; detailed TRICARE/CHAMPVA source gaps remain held. Research sources remain unapproved; no verified matching or enrollment capability.

## RC27 · Material exception/continuity

**Trigger / scope:** User/notice reports ESRD coordination, institutional stay, disaster, plan misconduct/termination, imminent coverage/refill gap or another source-listed exception. Do not screen everyone for every condition. **conditional · MVP recognition/referral; rare-case automation future.**

**Question:** Is there a coverage interruption you need help with now?

**Why we ask: An immediate gap may need a different next step.**

**Controls:** Yes + brief optional detail; No; Not sure; I want human help. Every question also supports Not sure, Check later/Defer, Back and Ask. Something else retains brief text and requires confirmed extraction; no invented enum. RC29/RC30 are boundary controls, not automatically queued questions.

**Proposed schema:** `{"exceptions.reported": "approved event enum + minimal wording", "exceptions.urgency": "reported|unknown", "exceptions.review": "pending evidence"}`. These are design fields, not fields currently accepted by the guest backend.

**Dependencies:** RC08.

**Resolution:** Route only to approved event child or unresolved human review; no new LLM-generated insurance branch.

**Ambiguity/contradiction:** Never translate serious illness to SNP eligibility, presume ESRD prevents MA enrollment, or infer an exception from vague urgency. No clinical triage/medical recommendation.

**Matching consequence:** Holds only affected timing/coordination/continuity assurances; no false safety guarantee.

**Exact runtime question:** Is there a coverage interruption you need help with now?

**Exact runtime options:** Yes; No; I want human help.

**Runtime fields:** choice only.

**Implemented/source-validation status:** Wired recognition/preparation; no claimed outside intervention. Research sources remain unapproved; no verified matching or enrollment capability.

## RC28 · Conflicting or ambiguous proposed facts

**Trigger / scope:** Same person/period has mutually exclusive confirmed reports, unconfirmed text interpretation, or a result conflicts with the profile. **integrity_guard · MVP.**

**Question:** Which detail should we use?

**Why we ask: These answers lead to different checks.**

**Controls:** Explicit existing fact A; Explicit existing fact B; They apply at different times + dates; Neither + text; Not sure. Every question also supports Not sure, Check later/Defer, Back and Ask. Something else retains brief text and requires confirmed extraction; no invented enum. RC29/RC30 are boundary controls, not automatically queued questions.

**Proposed schema:** `{"integrity.conflict": "field/value refs, not deleted facts", "integrity.resolution": "confirmed replacement link|unknown"}`. These are design fields, not fields currently accepted by the guest backend.

**Dependencies:** None; integrity guards run before dependent checks.

**Resolution:** One explicit resolution or defer; one clarification retry maximum, then held. Facts at different times may both remain valid.

**Ambiguity/contradiction:** A+B membership and MA are not intrinsically inconsistent. Do not silently pick newer-looking text or AI confidence; preserve history and prior confirmed answers.

**Matching consequence:** Only dependent capabilities held; no favorable default/ranking.

**Exact runtime question:** What should I correct about the specific detail we were discussing?

**Exact runtime options:** Original Medicare is current; Medicare Advantage is current; They apply at different times; Neither.

**Runtime fields:** choice only.

**Implemented/source-validation status:** Implemented by protected-report/within-reply guards and specific conversational confirmation. Generic registry question is not automatically queued. Research sources remain unapproved; no verified matching or enrollment capability.

## RC29 · Source/data capability guard

**Trigger / scope:** Rule/source missing, stale, future-year mismatched, expert review absent, API unavailable, acceptance registry pending, or requested capability unsupported. **system_no_question · MVP.**

**Question:** No question: show the specific unavailable check.

**Why we ask: Your answers cannot replace a missing source check.**

**Controls:** See limitations; Review saved answers; See labeled samples; Optional human help. Every question also supports Not sure, Check later/Defer, Back and Ask. Something else retains brief text and requires confirmed extraction; no invented enum. RC29/RC30 are boundary controls, not automatically queued questions.

**Proposed schema:** `{"capabilities.state": "not_supported|data_held|needs_facts|ready_for_scoped_check", "sources.receipt": "manifest/code/rule digest + approved review; null remains held"}`. These are design fields, not fields currently accepted by the guest backend.

**Dependencies:** None; integrity guards run before dependent checks.

**Resolution:** End affected data check with evidence-based state; do not collect irrelevant extra facts to conceal unavailable data.

**Ambiguity/contradiction:** A technically downloaded file or accurate LLM explanation is not an accepted consumer release. 2026 facts must not be relabeled 2027.

**Matching consequence:** Capabilities held independently. Current registry is pending, so readiness facts cannot release personalized matches.

**Implemented/source-validation status:** Active system guard/map and sample-plan limitations; no personal questions can replace missing data. Research sources remain unapproved; no verified matching or enrollment capability.

## RC30 · Final plan-specific review

**Trigger / scope:** Future user selects a plan and requests application/action. Never part of the initial readiness question queue. **post_selection_not_queue · Future; separate final gate.**

**Question:** Confirm the final plan and coverage dates before applying.

**Why we ask: An application needs a separate plan-specific review.**

**Controls:** Review plan/EOC/effective date; Confirm details through authorized process; Keep researching. Every question also supports Not sure, Check later/Defer, Back and Ask. Something else retains brief text and requires confirmed extraction; no invented enum. RC29/RC30 are boundary controls, not automatically queued questions.

**Proposed schema:** `{"application.readiness": "separate future state; no Medicare IDs in research profile"}`. These are design fields, not fields currently accepted by the guest backend.

**Dependencies:** RC29.

**Resolution:** Official/plan eligibility and plan-specific confirmations, consent and application permissions completed through separately authorized workflow.

**Ambiguity/contradiction:** Readiness report and source-reviewed comparison are not enrollment, legal eligibility or approved exceptions. Never cancel old coverage from a suggested match.

**Matching consequence:** Application/action held; comparison remains scoped and reversible.

**Implemented/source-validation status:** Deliberately held and outside intake; enrollment/cancellation is not implemented. Research sources remain unapproved; no verified matching or enrollment capability.
