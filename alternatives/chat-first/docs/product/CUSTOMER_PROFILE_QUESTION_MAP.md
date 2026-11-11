# Recovered question and customer-profile map

Recovered from the current original app/docs and the alternative on 23 October 2026. No new research or invented question target.

## Enumerated counts

**38 primary question IDs** = 10 baseline + RC01–RC28. **3 explicitly worded research child prompts** bring the enumerated primary/child prompt list to **41**. There are also **11 runtime clarification/variant templates**, which overlap parent/child information and are not 11 extra mandatory questions; and **31 detail controls**, including internal entity references and legacy supply wording, which are not 31 separate questions. RC29 and RC30 are **2 non-intake guards**. Per-doctor/per-medicine instances and missing-field combinations vary; there is no fixed total interview length.

The current runtime wording takes precedence over older research wording (for example RC15 reuses the Part B date through RC05). The full machine map contains all 52 parent/child/variant definitions with explicit kind/parent, fields, applicability and provenance. See `cms-slice/config/profile/question-map.json`, `customer-profile.template.json` and `customer-profile.schema.json`.

## Mapping and boundaries

Every leaf maps to existing `guide.fields` or `readiness.facts` storage. No second guest identity or database. Missing = unanswered; explicit none differs from unknown/deferred; tentative is not confirmed; reported is not verified. Optional preferences do not block basic availability. Required facts apply only to the requested capability and consequential existing branches. SSNs, Medicare numbers, credentials and unnecessary clinical details are outside this profile. External source/network/formulary/pricing/expert evidence remains a separate hold.

## Questions, child prompts and variants

### T01 · baseline

**Question:** What would you like help with today?

**Options:** Understand Medicare; Find coverage; Review existing coverage; Something else

**Fields:** `guide.fields.intent.goal`; `guide.fields.intent.goalDetail`

**Purpose:** Your goal tells Daylight what to explain and what to emphasize. We will work through your situation, needs and priorities in ten questions.

**Applicability / required:** Context/goal-based comparison preparation; browsing does not require completion. · required_only_for_relevant_capability

**Comparison scope:** route_comparison

**Dependencies:** Parent/current subject as applicable. **Stale on change:** intent.goal, intent.goalDetail.

**Evidence:** explicit user report or explicit unknown/deferred; never independently verified. Unknown/deferred never satisfies required facts. Source: `cms-slice/apps/ten-question/ten-state.js`.

### T02 · baseline

**Question:** How familiar are you with Medicare?

**Options:** New to Medicare; Know a little; Comfortable with the basics; Not sure yet

**Fields:** `guide.fields.knowledge.general`

**Purpose:** This sets how much explanation you see. It changes the detail, not the questions or the facts we need.

**Applicability / required:** Context/goal-based comparison preparation; browsing does not require completion. · optional_preference

**Comparison scope:** Optional preference / explanation depth.

**Dependencies:** Parent/current subject as applicable. **Stale on change:** knowledge.general.

**Evidence:** explicit user report or explicit unknown/deferred; never independently verified. Unknown/deferred never satisfies required facts. Source: `cms-slice/apps/ten-question/ten-state.js`.

### T03 · baseline

**Question:** What ZIP code do you live in?

**Options:** Typed entry / explicit unknown.

**Fields:** `guide.fields.comparison.scope.zip`; `guide.fields.comparison.scope.county`; `guide.fields.comparison.scope.locationEvidence`

**Purpose:** Plan availability and published prices can depend on the county. A ZIP lookup is a location reference, not proof of residency.

**Applicability / required:** Context/goal-based comparison preparation; browsing does not require completion. · required_only_for_relevant_capability

**Comparison scope:** availability

**Dependencies:** Parent/current subject as applicable. **Stale on change:** comparison.scope.zip, comparison.scope.county, comparison.scope.locationEvidence.

**Evidence:** explicit user report or explicit unknown/deferred; never independently verified. Unknown/deferred never satisfies required facts. Source: `cms-slice/apps/ten-question/ten-state.js`.

### T04 · baseline

**Question:** When do you need Medicare coverage to start?

**Options:** Choose a start month; Already on Medicare; Not sure

**Fields:** `guide.fields.coverage.requestedStart`; `guide.fields.coverage.requestedStartMonth`

**Purpose:** The timing helps organize what to check next. Your requested month does not establish eligibility or an enrollment deadline.

**Applicability / required:** Context/goal-based comparison preparation; browsing does not require completion. · required_only_for_relevant_capability

**Comparison scope:** timing

**Dependencies:** Parent/current subject as applicable. **Stale on change:** coverage.requestedStart, coverage.requestedStartMonth.

**Evidence:** explicit user report or explicit unknown/deferred; never independently verified. Unknown/deferred never satisfies required facts. Source: `cms-slice/apps/ten-question/ten-state.js`.

### T05 · baseline

**Question:** What health coverage do you have now?

**Options:** Original Medicare (Parts A and B); Medicare Advantage (Part C); Medicare Supplement / Medigap; Separate prescription drug plan; Current-job coverage; Retiree coverage; COBRA; VA, TRICARE or military coverage; Medicaid; None; Not sure

**Fields:** `guide.fields.coverage.current`

**Purpose:** We need to understand what is already in place before considering a change. Your answers describe your coverage; they do not verify its benefits.

**Applicability / required:** Context/goal-based comparison preparation; browsing does not require completion. · required_only_for_relevant_capability

**Comparison scope:** route_comparison

**Dependencies:** Parent/current subject as applicable. **Stale on change:** coverage.current.

**Evidence:** explicit user report or explicit unknown/deferred; never independently verified. Unknown/deferred never satisfies required facts. Source: `cms-slice/apps/ten-question/ten-state.js`.

### T06 · baseline

**Question:** Which doctors or hospitals would you like to keep?

**Options:** Add doctors or hospitals; None to check; Add later

**Fields:** `guide.fields.needs.providersStatus`; `guide.fields.needs.providers`

**Purpose:** Provider access is an important check before choosing coverage. A name alone does not establish participation or guarantee access.

**Applicability / required:** Context/goal-based comparison preparation; browsing does not require completion. · required_only_for_relevant_capability

**Comparison scope:** provider_fit

**Dependencies:** Parent/current subject as applicable. **Stale on change:** needs.providersStatus, needs.providers.

**Evidence:** explicit user report or explicit unknown/deferred; never independently verified. Unknown/deferred never satisfies required facts. Source: `cms-slice/apps/ten-question/ten-state.js`.

### T07 · baseline

**Question:** What prescriptions do you take?

**Options:** Add prescriptions; None; Add later

**Fields:** `guide.fields.needs.medicinesStatus`; `guide.fields.needs.medications`; `guide.fields.needs.medicationDetails`; `guide.fields.needs.pharmacies`

**Purpose:** Drug coverage and costs depend on the exact medicine and plan. Dose and pharmacy details can help later; unknown details can stay open.

**Applicability / required:** Context/goal-based comparison preparation; browsing does not require completion. · required_only_for_relevant_capability

**Comparison scope:** drug_coverage, drug_pricing

**Dependencies:** Parent/current subject as applicable. **Stale on change:** needs.medicinesStatus, needs.medications, needs.medicationDetails, needs.pharmacies.

**Evidence:** explicit user report or explicit unknown/deferred; never independently verified. Unknown/deferred never satisfies required facts. Source: `cms-slice/apps/ten-question/ten-state.js`.

### T08 · baseline

**Question:** Will you need routine care away from home?

**Options:** Local only; Another state; Outside the US; Not sure

**Fields:** `guide.fields.needs.travel`

**Purpose:** Routine care away from home can have different coverage limits from emergency care. Tell us where you expect to need routine care.

**Applicability / required:** Context/goal-based comparison preparation; browsing does not require completion. · required_only_for_relevant_capability

**Comparison scope:** provider_fit, route_comparison

**Dependencies:** Parent/current subject as applicable. **Stale on change:** needs.travel.

**Evidence:** explicit user report or explicit unknown/deferred; never independently verified. Unknown/deferred never satisfies required facts. Source: `cms-slice/apps/ten-question/ten-state.js`.

### T09 · baseline

**Question:** How would you prefer to balance monthly payments and costs when you get care?

**Options:** Lower monthly payments; More predictable costs; No preference yet

**Fields:** `guide.fields.needs.costPreference`

**Purpose:** This helps us explain the tradeoffs you care about. It is not enough by itself to choose a coverage route or calculate your total costs.

**Applicability / required:** Context/goal-based comparison preparation; browsing does not require completion. · optional_preference

**Comparison scope:** Optional preference / explanation depth.

**Dependencies:** Parent/current subject as applicable. **Stale on change:** needs.costPreference.

**Evidence:** explicit user report or explicit unknown/deferred; never independently verified. Unknown/deferred never satisfies required facts. Source: `cms-slice/apps/ten-question/ten-state.js`.

### T10 · baseline

**Question:** What matters most when we compare your options?

**Options:** Doctors and hospitals; Prescriptions; Total cost; Predictable costs; Travel; Something else; Not sure

**Fields:** `guide.fields.needs.priorities`; `guide.fields.needs.priorityOther`

**Purpose:** Your priorities should guide the comparison, independently of commissions or other commercial relationships. Choose up to three.

**Applicability / required:** Context/goal-based comparison preparation; browsing does not require completion. · optional_preference

**Comparison scope:** Optional preference / explanation depth.

**Dependencies:** Parent/current subject as applicable. **Stale on change:** needs.priorities, needs.priorityOther.

**Evidence:** explicit user report or explicit unknown/deferred; never independently verified. Unknown/deferred never satisfies required facts. Source: `cms-slice/apps/ten-question/ten-state.js`.

### RC01 · conditional

**Question:** Who is this coverage for?

**Options:** Me; Someone I help; Research only

**Fields:** `readiness.facts.RC01.value.choice`

**Purpose:** Why we ask: We need to keep one person’s details together.

**Applicability / required:** A personal comparison is requested and recipient or requested capability is unconfirmed. Reuse a confirmed Ask fact; education-only may bypass. **baseline_by_capability · MVP.** · required_only_when_applicable_to_requested_check

**Comparison scope:** route_comparison

**Dependencies:** None; integrity guards run before dependent checks. **Stale on change:** coverage.current, relevant_parent_report.

**Evidence:** explicit user report or explicit unknown/deferred; never independently verified. Unknown/deferred never satisfies required facts. Source: `cms-slice/apps/ten-question/readiness-content.json + docs/product/READINESS_TRIGGERS.md`.

### RC02 · conditional

**Question:** Where is your permanent home?

**Options:** Add the details I know

**Fields:** `readiness.facts.RC02.value.choice`; `readiness.facts.RC02.value.zip`; `readiness.facts.RC02.value.county`; `readiness.facts.RC02.value.homeStatus`

**Purpose:** Why we ask: Plan availability depends on where you live.

**Applicability / required:** Requested availability/network check lacks usable home ZIP/county, spans counties, or moving/seasonal facts conflict with home. **baseline_by_capability · MVP.** · required_only_when_applicable_to_requested_check

**Comparison scope:** availability

**Dependencies:** RC01. **Stale on change:** comparison.scope.zip, comparison.scope.county.

**Evidence:** explicit user report or explicit unknown/deferred; never independently verified. Unknown/deferred never satisfies required facts. Source: `cms-slice/apps/ten-question/readiness-content.json + docs/product/READINESS_TRIGGERS.md`.

### RC03 · conditional

**Question:** Which year should we compare?

**Options:** 2026; 2027; Another year

**Fields:** `readiness.facts.RC03.value.choice`; `readiness.facts.RC03.value.year`

**Purpose:** Why we ask: Plan benefits and prices can change each year.

**Applicability / required:** Requested benefit year/start is unknown, mismatches source year, or already-on-Medicare answer supplied no comparison year. **baseline_by_capability · MVP.** · required_only_when_applicable_to_requested_check

**Comparison scope:** availability

**Dependencies:** RC01. **Stale on change:** coverage.requestedStart, coverage.requestedStartMonth.

**Evidence:** explicit user report or explicit unknown/deferred; never independently verified. Unknown/deferred never satisfies required facts. Source: `cms-slice/apps/ten-question/readiness-content.json + docs/product/READINESS_TRIGGERS.md`.

### RC04 · conditional

**Question:** Which Medicare parts do you have now?

**Options:** A and B; A only; B only; Neither; Applied; waiting

**Fields:** `readiness.facts.RC04.value.choice`

**Purpose:** Why we ask: Different plans require different Medicare parts.

**Applicability / required:** Personal health/drug candidates requested and active/pending Part A/Part B status is not independently represented; Q4 Already on Medicare is insufficient. **baseline_by_capability · MVP.** · required_only_when_applicable_to_requested_check

**Comparison scope:** timing, route_comparison

**Dependencies:** RC01. **Stale on change:** coverage.current, relevant_parent_report.

**Evidence:** explicit user report or explicit unknown/deferred; never independently verified. Unknown/deferred never satisfies required facts. Source: `cms-slice/apps/ten-question/readiness-content.json + docs/product/READINESS_TRIGGERS.md`.

### RC05 · conditional

**Question:** When did Part B start?

**Options:** Add the details I know

**Fields:** `readiness.facts.RC05.value.choice`; `readiness.facts.RC05.value.month`

**Purpose:** Why we ask: This can affect your enrollment and Medigap options.

**Applicability / required:** Timing/Medigap/change review needs actual A/B dates and they are missing or different from requested start. **baseline_by_capability · MVP.** · required_only_when_applicable_to_requested_check

**Comparison scope:** timing, medigap_rights

**Dependencies:** RC04. **Stale on change:** coverage.current, relevant_parent_report.

**Evidence:** explicit user report or explicit unknown/deferred; never independently verified. Unknown/deferred never satisfies required facts. Source: `cms-slice/apps/ten-question/readiness-content.json + docs/product/READINESS_TRIGGERS.md`.

### RC06 · conditional

**Question:** How did you first qualify, or expect to qualify, for Medicare?

**Options:** Age 65 or older; Disability before 65; Kidney failure / ESRD; ALS; Another reason

**Fields:** `readiness.facts.RC06.value.choice`; `readiness.facts.RC06.value.ageBand`

**Purpose:** Why we ask: Some enrollment rules depend on how you qualified.

**Applicability / required:** Timing, premium eligibility or Medigap rights need age/basis that existing confirmed enrollment does not resolve; not a universal diagnosis screen. **conditional · MVP.** · required_only_when_applicable_to_requested_check

**Comparison scope:** timing, medigap_rights

**Dependencies:** RC04. **Stale on change:** coverage.current, relevant_parent_report.

**Evidence:** explicit user report or explicit unknown/deferred; never independently verified. Unknown/deferred never satisfies required facts. Source: `cms-slice/apps/ten-question/readiness-content.json + docs/product/READINESS_TRIGGERS.md`.

### RC07 · conditional

**Question:** How do you get your A and B benefits now?

**Options:** Original Medicare; Medicare Advantage; A change is pending

**Fields:** `readiness.facts.RC07.value.choice`

**Purpose:** Why we ask: We need to separate current coverage from a possible change.

**Applicability / required:** Current medical arrangement has incompatible same-period reports or user wants to leave MA/Medigap without a clear current-versus-future distinction. **conditional · MVP.** · required_only_when_applicable_to_requested_check

**Comparison scope:** route_comparison, medigap_rights

**Dependencies:** RC04. **Stale on change:** coverage.current, relevant_parent_report.

**Evidence:** explicit user report or explicit unknown/deferred; never independently verified. Unknown/deferred never satisfies required facts. Source: `cms-slice/apps/ten-question/readiness-content.json + docs/product/READINESS_TRIGGERS.md`.

### RC08 · conditional

**Question:** What changed about your coverage?

**Options:** Losing coverage; Moving; Plan ending or changing service area; Medicaid or Extra Help changed; Another event; Nothing changed

**Fields:** `readiness.facts.RC08.value.choice`; `readiness.facts.RC08.value.eventDate`

**Purpose:** Why we ask: This can affect when you can enroll.

**Applicability / required:** User requests a change/start outside an established reviewed window, or reports move, loss, plan termination, institutional stay, disaster or other potential event. **conditional · MVP.** · required_only_when_applicable_to_requested_check

**Comparison scope:** timing

**Dependencies:** RC03, RC04, RC07. **Stale on change:** coverage.current, relevant_parent_report.

**Evidence:** explicit user report or explicit unknown/deferred; never independently verified. Unknown/deferred never satisfies required facts. Source: `cms-slice/apps/ten-question/readiness-content.json + docs/product/READINESS_TRIGGERS.md`.

### RC09 · conditional

**Question:** Is this coverage from someone who is still working?

**Options:** My current job; Spouse’s current job; Family member’s current job; Retiree coverage; COBRA

**Fields:** `readiness.facts.RC09.value.choice`

**Purpose:** Why we ask: Current work can affect your Medicare sign-up window.

**Applicability / required:** Q5 employer/retiree/COBRA or free text indicates job-related insurance, but source of coverage/current-work relationship unclear. **conditional · MVP.** · required_only_when_applicable_to_requested_check

**Comparison scope:** timing

**Dependencies:** RC07. **Stale on change:** coverage.current, relevant_parent_report.

**Evidence:** explicit user report or explicit unknown/deferred; never independently verified. Unknown/deferred never satisfies required facts. Source: `cms-slice/apps/ten-question/readiness-content.json + docs/product/READINESS_TRIGGERS.md`.

### RC10 · conditional

**Question:** Does the employer have 20 or more employees?

**Options:** Yes; No

**Fields:** `readiness.facts.RC10.value.choice`

**Purpose:** Why we ask: Employer size can change which coverage pays first.

**Applicability / required:** Current group coverage plus payer-order question; age/basis known. Do not run age threshold for ESRD. **conditional · MVP.** · required_only_when_applicable_to_requested_check

**Comparison scope:** timing

**Dependencies:** RC06, RC09. **Stale on change:** coverage.current, relevant_parent_report.

**Evidence:** explicit user report or explicit unknown/deferred; never independently verified. Unknown/deferred never satisfies required facts. Source: `cms-slice/apps/ten-question/readiness-content.json + docs/product/READINESS_TRIGGERS.md`.

### RC11 · conditional

**Question:** When did the job or coverage end?

**Options:** Add the end dates I know; Still working

**Fields:** `readiness.facts.RC11.value.choice`; `readiness.facts.RC11.value.jobEnd`; `readiness.facts.RC11.value.coverageEnd`

**Purpose:** Why we ask: Different end dates can change your sign-up window.

**Applicability / required:** Coverage/job ending or ended, COBRA/retiree transition, or prospective change needs loss chronology. **conditional · MVP.** · required_only_when_applicable_to_requested_check

**Comparison scope:** timing

**Dependencies:** RC09. **Stale on change:** coverage.current, relevant_parent_report.

**Evidence:** explicit user report or explicit unknown/deferred; never independently verified. Unknown/deferred never satisfies required facts. Source: `cms-slice/apps/ten-question/readiness-content.json + docs/product/READINESS_TRIGGERS.md`.

### RC12 · conditional

**Question:** Do you have a written notice saying your drug coverage counts as creditable (as good as Medicare’s standard coverage), and has there been a gap?

**Options:** Yes, according to its notice; No; I have no drug coverage

**Fields:** `readiness.facts.RC12.value.choice`; `readiness.facts.RC12.value.gap`

**Purpose:** Why we ask: A gap in qualifying drug coverage can affect later costs.

**Applicability / required:** Part D is absent/ending/unknown and employer/retiree/military/other drug coverage might exist, or user proposes no drug coverage. **conditional · MVP.** · required_only_when_applicable_to_requested_check

**Comparison scope:** timing, drug_coverage

**Dependencies:** RC07, RC09. **Stale on change:** coverage.current, relevant_parent_report.

**Evidence:** explicit user report or explicit unknown/deferred; never independently verified. Unknown/deferred never satisfies required facts. Source: `cms-slice/apps/ten-question/readiness-content.json + docs/product/READINESS_TRIGGERS.md`.

### RC13 · conditional

**Question:** Could a change affect anyone else’s coverage?

**Options:** Administrator says yes; Administrator says no; I have not checked

**Fields:** `readiness.facts.RC13.value.choice`

**Purpose:** Why we ask: Some changes can affect family or retiree benefits.

**Applicability / required:** Employer/union/retiree coverage exists and user considers joining outside MA/PDP or dropping group coverage. **conditional · MVP.** · required_only_when_applicable_to_requested_check

**Comparison scope:** timing, route_comparison

**Dependencies:** RC09. **Stale on change:** coverage.current, relevant_parent_report.

**Evidence:** explicit user report or explicit unknown/deferred; never independently verified. Unknown/deferred never satisfies required facts. Source: `cms-slice/apps/ten-question/readiness-content.json + docs/product/READINESS_TRIGGERS.md`.

### RC14 · conditional

**Question:** Are you or your employer adding money to an HSA?

**Options:** Yes; No

**Fields:** `readiness.facts.RC14.value.choice`

**Purpose:** Why we ask: Medicare start dates can affect HSA contributions.

**Applicability / required:** User reports current-work coverage, Medicare deferral/retroactive A or specifically mentions HSA contributions. **conditional · MVP.** · required_only_when_applicable_to_requested_check

**Comparison scope:** timing

**Dependencies:** RC05, RC09. **Stale on change:** coverage.current, relevant_parent_report.

**Evidence:** explicit user report or explicit unknown/deferred; never independently verified. Unknown/deferred never satisfies required facts. Source: `cms-slice/apps/ten-question/readiness-content.json + docs/product/READINESS_TRIGGERS.md`.

### RC15 · conditional

**Question:** For the Medigap option you want to explore, what coverage change or notice should we check?

**Options:** Relevant change or notice; No change or notice known

**Fields:** `readiness.facts.RC15.value.choice`; `readiness.facts.RC15.value.event`

**Purpose:** Why we ask: This can affect your Medigap purchase rights.

**Applicability / required:** Original+Medigap purchase/replacement path requested; age, basis, Part B start or qualifying group-loss dates are missing or not reviewed. **conditional · MVP.** · required_only_when_applicable_to_requested_check

**Comparison scope:** medigap_rights

**Dependencies:** RC02, RC05, RC06, RC11. **Stale on change:** coverage.current, relevant_parent_report.

**Evidence:** explicit user report or explicit unknown/deferred; never independently verified. Unknown/deferred never satisfies required facts. Source: `cms-slice/apps/ten-question/readiness-content.json + docs/product/READINESS_TRIGGERS.md`.

### RC16 · conditional

**Question:** Was this your first Medicare Advantage plan, when did it start, and did you have Medigap before?

**Options:** Yes; No

**Fields:** `readiness.facts.RC16.value.choice`; `readiness.facts.RC16.value.start`; `readiness.facts.RC16.value.priorMedigap`

**Purpose:** Why we ask: Your coverage history may affect Medigap rights.

**Applicability / required:** Current/recent MA plus interest in Original+Medigap, lost supplement, plan termination/move or alleged insurer misconduct. **conditional · MVP.** · required_only_when_applicable_to_requested_check

**Comparison scope:** medigap_rights

**Dependencies:** RC07, RC08, RC15. **Stale on change:** coverage.current, relevant_parent_report.

**Evidence:** explicit user report or explicit unknown/deferred; never independently verified. Unknown/deferred never satisfies required facts. Source: `cms-slice/apps/ten-question/readiness-content.json + docs/product/READINESS_TRIGGERS.md`.

### RC17 · conditional

**Question:** Are you replacing an existing Medigap policy?

**Options:** Yes, replacing it; No, keeping it

**Fields:** `readiness.facts.RC17.value.choice`

**Purpose:** Why we ask: You may not have the same rights to buy it again.

**Applicability / required:** User already has Medigap and wants another supplement/carrier or is considering dropping it. **conditional · MVP.** · required_only_when_applicable_to_requested_check

**Comparison scope:** medigap_rights

**Dependencies:** RC07, RC15. **Stale on change:** coverage.current, relevant_parent_report.

**Evidence:** explicit user report or explicit unknown/deferred; never independently verified. Unknown/deferred never satisfies required facts. Source: `cms-slice/apps/ten-question/readiness-content.json + docs/product/READINESS_TRIGGERS.md`.

### RC18 · conditional

**Question:** Do you get help with Medicare costs now? You can name more than one program.

**Options:** Medicaid; Extra Help; Help paying Part B; SSI; None known; Prefer not to say

**Fields:** `readiness.facts.RC18.value.choice`

**Purpose:** Why we ask: Assistance can change what you pay.

**Applicability / required:** Subsidy-adjusted costs, a reported Medicaid program, affordability concern or explicit help request makes program status consequential. **conditional · MVP.** · required_only_when_applicable_to_requested_check

**Comparison scope:** drug_pricing, snp

**Dependencies:** RC01, RC03. **Stale on change:** coverage.current, relevant_parent_report.

**Evidence:** explicit user report or explicit unknown/deferred; never independently verified. Unknown/deferred never satisfies required facts. Source: `cms-slice/apps/ten-question/readiness-content.json + docs/product/READINESS_TRIGGERS.md`.

### RC19 · conditional

**Question:** For the Special Needs Plan type you want to explore, what exact qualifying program or plan confirmation do you have?

**Options:** Program or plan confirmation; No confirmation; Do not explore this type

**Fields:** `readiness.facts.RC19.value.choice`; `readiness.facts.RC19.value.qualification`

**Purpose:** Why we ask: These plans have additional requirements; your report still needs independent verification.

**Applicability / required:** User asks about an SNP or volunteers Medicaid/qualifying institutional/chronic circumstances and a supported candidate actually requires them. **conditional · MVP flags/referral; detailed SNP matching future.** · required_only_when_applicable_to_requested_check

**Comparison scope:** snp

**Dependencies:** RC02, RC04, RC18. **Stale on change:** coverage.current, relevant_parent_report.

**Evidence:** explicit user report or explicit unknown/deferred; never independently verified. Unknown/deferred never satisfies required facts. Source: `cms-slice/apps/ten-question/readiness-content.json + docs/product/READINESS_TRIGGERS.md`.

### RC20 · conditional

**Question:** Where will you need routine care away from home?

**Options:** Another U.S. state; Outside the U.S.; Emergency travel cover only

**Fields:** `readiness.facts.RC20.value.choice`; `readiness.facts.RC20.value.location`

**Purpose:** Why we ask: Routine care and emergency care can have different coverage.

**Applicability / required:** Q8 another-state/outside-US/unknown or moving/seasonal facts make care locations material to requested provider/travel fit. **conditional · MVP.** · required_only_when_applicable_to_requested_check

**Comparison scope:** provider_fit

**Dependencies:** RC02. **Stale on change:** needs.travel.

**Evidence:** explicit user report or explicit unknown/deferred; never independently verified. Unknown/deferred never satisfies required facts. Source: `cms-slice/apps/ten-question/readiness-content.json + docs/product/READINESS_TRIGGERS.md`.

### RC21 · conditional

**Question:** What exact office and location should we use for each doctor or hospital?

**Options:** Add practice and location; No longer needed

**Fields:** `readiness.facts.RC21.value.choice`; `readiness.facts.RC21.value.items[].entity`; `readiness.facts.RC21.value.items[].practice`; `readiness.facts.RC21.value.items[].city`

**Purpose:** Why we ask: The office location can affect the network check.

**Applicability / required:** Provider-fit requested and Q6 names are unresolved, ambiguous, location-free, or source/network result unavailable. **conditional · MVP.** · required_only_when_applicable_to_requested_check

**Comparison scope:** provider_fit

**Dependencies:** RC02, RC03. **Stale on change:** needs.providersStatus, needs.providers.

**Evidence:** explicit user report or explicit unknown/deferred; never independently verified. Unknown/deferred never satisfies required facts. Source: `cms-slice/apps/ten-question/readiness-content.json + docs/product/READINESS_TRIGGERS.md`.

### RC22 · conditional

**Question:** What exact name, strength, form, and brand or generic preference should we use for each medicine?

**Options:** Add exact name, strength and form; No longer taking

**Fields:** `readiness.facts.RC22.value.choice`; `readiness.facts.RC22.value.items[].entity`; `readiness.facts.RC22.value.items[].name`; `readiness.facts.RC22.value.items[].strength`; `readiness.facts.RC22.value.items[].form`; `readiness.facts.RC22.value.items[].brand`

**Purpose:** Why we ask: Strength and form can change the coverage check.

**Applicability / required:** Drug-fit/cost requested and medication string lacks a unique ingredient/brand, strength or form; preserve original wording. **conditional · MVP.** · required_only_when_applicable_to_requested_check

**Comparison scope:** drug_coverage, drug_pricing

**Dependencies:** RC03. **Stale on change:** needs.medicinesStatus, needs.medications, needs.medicationDetails.

**Evidence:** explicit user report or explicit unknown/deferred; never independently verified. Unknown/deferred never satisfies required facts. Source: `cms-slice/apps/ten-question/readiness-content.json + docs/product/READINESS_TRIGGERS.md`.

### RC23 · conditional

**Question:** For each medicine, what quantity, days supply, exact pharmacy and retail or mail order should we use?

**Options:** Add supply and pharmacy; Mail order

**Fields:** `readiness.facts.RC23.value.choice`; `readiness.facts.RC23.value.items[].entity`; `readiness.facts.RC23.value.items[].quantity`; `readiness.facts.RC23.value.items[].daysSupply`; `readiness.facts.RC23.value.items[].pharmacy`; `readiness.facts.RC23.value.items[].channel`; `readiness.facts.RC23.value.items[].supply`

**Purpose:** Why we ask: Supply and pharmacy can change the price.

**Applicability / required:** A drug-cost check is requested and days supply/quantity/fill channel or exact pharmacy is missing. **conditional · MVP.** · required_only_when_applicable_to_requested_check

**Comparison scope:** drug_pricing

**Dependencies:** RC22. **Stale on change:** needs.medications, needs.pharmacies, RC22.

**Evidence:** explicit user report or explicit unknown/deferred; never independently verified. Unknown/deferred never satisfies required facts. Source: `cms-slice/apps/ten-question/readiness-content.json + docs/product/READINESS_TRIGGERS.md`.

### RC24 · conditional

**Question:** Is this given at a clinic or filled at a pharmacy?

**Options:** At a clinic; At a pharmacy; Both / Not sure

**Fields:** `readiness.facts.RC24.value.choice`

**Purpose:** Why we ask: Some medicines use different Medicare coverage rules.

**Applicability / required:** Validated source flags PA/ST/quantity restrictions, administration setting is ambiguous, or user reports a current exception/coverage problem. **conditional · MVP.** · required_only_when_applicable_to_requested_check

**Comparison scope:** drug_coverage

**Dependencies:** RC22, RC23. **Stale on change:** coverage.current, relevant_parent_report.

**Evidence:** explicit user report or explicit unknown/deferred; never independently verified. Unknown/deferred never satisfies required facts. Source: `cms-slice/apps/ten-question/readiness-content.json + docs/product/READINESS_TRIGGERS.md`.

### RC25 · conditional

**Question:** Is there a monthly amount you want to stay under?

**Options:** Add an optional budget; No fixed limit; Prefer not to say

**Fields:** `readiness.facts.RC25.value.choice`; `readiness.facts.RC25.value.amount`; `readiness.facts.RC25.value.includes`

**Purpose:** Why we ask: A low plan premium is not the whole cost.

**Applicability / required:** Cost priority or numeric budget request is material; Q9 cost preference alone does not establish affordability or total annual spending. **conditional · MVP.** · optional_preference

**Comparison scope:** Optional preference / explanation depth.

**Dependencies:** RC03, RC18. **Stale on change:** coverage.current, relevant_parent_report.

**Evidence:** explicit user report or explicit unknown/deferred; never independently verified. Unknown/deferred never satisfies required facts. Source: `cms-slice/apps/ten-question/readiness-content.json + docs/product/READINESS_TRIGGERS.md`.

### RC26 · conditional

**Question:** Which military or veterans’ coverage do you have?

**Options:** VA health care; TRICARE For Life; Other TRICARE; CHAMPVA; Another program

**Fields:** `readiness.facts.RC26.value.choice`

**Purpose:** Why we ask: These programs work with Medicare in different ways.

**Applicability / required:** Q5 military category or free text indicates VA, TRICARE, CHAMPVA or another federal program without exact program context. **conditional · MVP.** · required_only_when_applicable_to_requested_check

**Comparison scope:** timing, route_comparison

**Dependencies:** RC04, RC12. **Stale on change:** coverage.current, relevant_parent_report.

**Evidence:** explicit user report or explicit unknown/deferred; never independently verified. Unknown/deferred never satisfies required facts. Source: `cms-slice/apps/ten-question/readiness-content.json + docs/product/READINESS_TRIGGERS.md`.

### RC27 · conditional

**Question:** Is there a coverage interruption you need help with now?

**Options:** Yes; No; I want human help

**Fields:** `readiness.facts.RC27.value.choice`

**Purpose:** Why we ask: An immediate gap may need a different next step.

**Applicability / required:** User/notice reports ESRD coordination, institutional stay, disaster, plan misconduct/termination, imminent coverage/refill gap or another source-listed exception. Do not screen everyone for every condition. **conditional · MVP recognition/referral; rare-case automation future.** · required_only_when_applicable_to_requested_check

**Comparison scope:** timing

**Dependencies:** RC08. **Stale on change:** coverage.current, relevant_parent_report.

**Evidence:** explicit user report or explicit unknown/deferred; never independently verified. Unknown/deferred never satisfies required facts. Source: `cms-slice/apps/ten-question/readiness-content.json + docs/product/READINESS_TRIGGERS.md`.

### RC28 · conditional

**Question:** What should I correct about the specific detail we were discussing?

**Options:** Original Medicare is current; Medicare Advantage is current; They apply at different times; Neither

**Fields:** `readiness.facts.RC28.value.choice`

**Purpose:** Why we ask: These answers lead to different checks.

**Applicability / required:** Same person/period has mutually exclusive confirmed reports, unconfirmed text interpretation, or a result conflicts with the profile. **integrity_guard · MVP.** · required_only_when_applicable_to_requested_check

**Comparison scope:** route_comparison

**Dependencies:** None; integrity guards run before dependent checks. **Stale on change:** coverage.current, relevant_parent_report.

**Evidence:** explicit user report or explicit unknown/deferred; never independently verified. Unknown/deferred never satisfies required facts. Source: `cms-slice/apps/ten-question/readiness-content.json + docs/product/READINESS_TRIGGERS.md`.

### RC11.C1 · documented_child

**Question:** When does the job-based health coverage end?

**Options:** Add the end dates I know; Still working

**Fields:** `readiness.facts.RC11.value.coverageEnd`

**Purpose:** Why we ask: Different end dates can change your sign-up window.

**Applicability / required:** Only the missing child detail/variant of RC11; deduplicate against the parent report. · required_only_when_applicable_to_requested_check

**Comparison scope:** timing

**Dependencies:** RC09. **Stale on change:** coverage.current, relevant_parent_report.

**Evidence:** explicit user report or explicit unknown/deferred; never independently verified. Unknown/deferred never satisfies required facts. Source: `docs/product/READINESS_TRIGGERS.md`.

### RC16.C1 · documented_child

**Question:** When did it start?

**Options:** Yes; No

**Fields:** `readiness.facts.RC16.value.start`

**Purpose:** Why we ask: Your coverage history may affect Medigap rights.

**Applicability / required:** Only the missing child detail/variant of RC16; deduplicate against the parent report. · required_only_when_applicable_to_requested_check

**Comparison scope:** medigap_rights

**Dependencies:** RC07, RC08, RC15. **Stale on change:** coverage.current, relevant_parent_report.

**Evidence:** explicit user report or explicit unknown/deferred; never independently verified. Unknown/deferred never satisfies required facts. Source: `docs/product/READINESS_TRIGGERS.md`.

### RC16.C2 · documented_child

**Question:** Did you have Medigap before it?

**Options:** Yes; No

**Fields:** `readiness.facts.RC16.value.priorMedigap`

**Purpose:** Why we ask: Your coverage history may affect Medigap rights.

**Applicability / required:** Only the missing child detail/variant of RC16; deduplicate against the parent report. · required_only_when_applicable_to_requested_check

**Comparison scope:** medigap_rights

**Dependencies:** RC07, RC08, RC15. **Stale on change:** coverage.current, relevant_parent_report.

**Evidence:** explicit user report or explicit unknown/deferred; never independently verified. Unknown/deferred never satisfies required facts. Source: `docs/product/READINESS_TRIGGERS.md`.

### RC02.V1 · runtime_variant

**Question:** Which county and state is your permanent home in?

**Options:** Add the details I know

**Fields:** `readiness.facts.RC02.value.county`

**Purpose:** Why we ask: Plan availability depends on where you live.

**Applicability / required:** Only the missing child detail/variant of RC02; deduplicate against the parent report. · required_only_when_applicable_to_requested_check

**Comparison scope:** availability

**Dependencies:** RC01. **Stale on change:** comparison.scope.zip, comparison.scope.county.

**Evidence:** explicit user report or explicit unknown/deferred; never independently verified. Unknown/deferred never satisfies required facts. Source: `cms-slice/apps/ten-question/readiness-core.js::question`.

### RC02.V2 · runtime_variant

**Question:** What is your permanent home ZIP?

**Options:** Add the details I know

**Fields:** `readiness.facts.RC02.value.zip`

**Purpose:** Why we ask: Plan availability depends on where you live.

**Applicability / required:** Only the missing child detail/variant of RC02; deduplicate against the parent report. · required_only_when_applicable_to_requested_check

**Comparison scope:** availability

**Dependencies:** RC01. **Stale on change:** comparison.scope.zip, comparison.scope.county.

**Evidence:** explicit user report or explicit unknown/deferred; never independently verified. Unknown/deferred never satisfies required facts. Source: `cms-slice/apps/ten-question/readiness-core.js::question`.

### RC02.V3 · runtime_variant

**Question:** Which ZIP and county will be your permanent home? Tell me whether you are moving or splitting time between homes.

**Options:** Add the details I know

**Fields:** `readiness.facts.RC02.value.zip`; `readiness.facts.RC02.value.county`; `readiness.facts.RC02.value.homeStatus`

**Purpose:** Why we ask: Plan availability depends on where you live.

**Applicability / required:** Only the missing child detail/variant of RC02; deduplicate against the parent report. · required_only_when_applicable_to_requested_check

**Comparison scope:** availability

**Dependencies:** RC01. **Stale on change:** comparison.scope.zip, comparison.scope.county.

**Evidence:** explicit user report or explicit unknown/deferred; never independently verified. Unknown/deferred never satisfies required facts. Source: `cms-slice/apps/ten-question/readiness-core.js::question`.

### RC10.V1 · runtime_variant

**Question:** Does the employer have 100 or more employees?

**Options:** Yes; No

**Fields:** `readiness.facts.RC10.value.choice`

**Purpose:** Why we ask: Employer size can change which coverage pays first.

**Applicability / required:** Only the missing child detail/variant of RC10; deduplicate against the parent report. · required_only_when_applicable_to_requested_check

**Comparison scope:** timing

**Dependencies:** RC06, RC09. **Stale on change:** coverage.current, relevant_parent_report.

**Evidence:** explicit user report or explicit unknown/deferred; never independently verified. Unknown/deferred never satisfies required facts. Source: `cms-slice/apps/ten-question/readiness-core.js::question`.

### RC11.V1 · runtime_variant

**Question:** What {missing job end / coverage end date fields} should I use?

**Options:** Add the end dates I know; Still working

**Fields:** `readiness.facts.RC11.value.jobEnd`; `readiness.facts.RC11.value.coverageEnd`

**Purpose:** Why we ask: Different end dates can change your sign-up window.

**Applicability / required:** Only the missing child detail/variant of RC11; deduplicate against the parent report. · required_only_when_applicable_to_requested_check

**Comparison scope:** timing

**Dependencies:** RC09. **Stale on change:** coverage.current, relevant_parent_report.

**Evidence:** explicit user report or explicit unknown/deferred; never independently verified. Unknown/deferred never satisfies required facts. Source: `cms-slice/apps/ten-question/readiness-core.js::question`.

### RC12.V1 · runtime_variant

**Question:** Has there been any gap in that drug coverage? If so, when?

**Options:** Yes, according to its notice; No; I have no drug coverage

**Fields:** `readiness.facts.RC12.value.gap`

**Purpose:** Why we ask: A gap in qualifying drug coverage can affect later costs.

**Applicability / required:** Only the missing child detail/variant of RC12; deduplicate against the parent report. · required_only_when_applicable_to_requested_check

**Comparison scope:** timing, drug_coverage

**Dependencies:** RC07, RC09. **Stale on change:** coverage.current, relevant_parent_report.

**Evidence:** explicit user report or explicit unknown/deferred; never independently verified. Unknown/deferred never satisfies required facts. Source: `cms-slice/apps/ten-question/readiness-core.js::question`.

### RC16.V1 · runtime_variant

**Question:** What {missing Advantage start / prior Medigap fields} should I use?

**Options:** Yes; No

**Fields:** `readiness.facts.RC16.value.start`; `readiness.facts.RC16.value.priorMedigap`

**Purpose:** Why we ask: Your coverage history may affect Medigap rights.

**Applicability / required:** Only the missing child detail/variant of RC16; deduplicate against the parent report. · required_only_when_applicable_to_requested_check

**Comparison scope:** medigap_rights

**Dependencies:** RC07, RC08, RC15. **Stale on change:** coverage.current, relevant_parent_report.

**Evidence:** explicit user report or explicit unknown/deferred; never independently verified. Unknown/deferred never satisfies required facts. Source: `cms-slice/apps/ten-question/readiness-core.js::question`.

### RC21.V1 · runtime_variant

**Question:** For {listed provider}, what {missing practice / office fields} should I use?

**Options:** Add practice and location; No longer needed

**Fields:** `readiness.facts.RC21.value.items[].practice`; `readiness.facts.RC21.value.items[].city`

**Purpose:** Why we ask: The office location can affect the network check.

**Applicability / required:** Only the missing child detail/variant of RC21; deduplicate against the parent report. · required_only_when_applicable_to_requested_check

**Comparison scope:** provider_fit

**Dependencies:** RC02, RC03. **Stale on change:** needs.providersStatus, needs.providers.

**Evidence:** explicit user report or explicit unknown/deferred; never independently verified. Unknown/deferred never satisfies required facts. Source: `cms-slice/apps/ten-question/readiness-core.js::question`.

### RC22.V1 · runtime_variant

**Question:** For {listed medicine}, what {missing exact identity fields} should I use?

**Options:** Add exact name, strength and form; No longer taking

**Fields:** `readiness.facts.RC22.value.items[].name`; `readiness.facts.RC22.value.items[].strength`; `readiness.facts.RC22.value.items[].form`; `readiness.facts.RC22.value.items[].brand`

**Purpose:** Why we ask: Strength and form can change the coverage check.

**Applicability / required:** Only the missing child detail/variant of RC22; deduplicate against the parent report. · required_only_when_applicable_to_requested_check

**Comparison scope:** drug_coverage, drug_pricing

**Dependencies:** RC03. **Stale on change:** needs.medicinesStatus, needs.medications, needs.medicationDetails.

**Evidence:** explicit user report or explicit unknown/deferred; never independently verified. Unknown/deferred never satisfies required facts. Source: `cms-slice/apps/ten-question/readiness-core.js::question`.

### RC23.V1 · runtime_variant

**Question:** For {listed medicine}, what {missing fill fields} should I use?

**Options:** Add supply and pharmacy; Mail order

**Fields:** `readiness.facts.RC23.value.items[].quantity`; `readiness.facts.RC23.value.items[].daysSupply`; `readiness.facts.RC23.value.items[].pharmacy`; `readiness.facts.RC23.value.items[].channel`

**Purpose:** Why we ask: Supply and pharmacy can change the price.

**Applicability / required:** Only the missing child detail/variant of RC23; deduplicate against the parent report. · required_only_when_applicable_to_requested_check

**Comparison scope:** drug_pricing

**Dependencies:** RC22. **Stale on change:** needs.medications, needs.pharmacies, RC22.

**Evidence:** explicit user report or explicit unknown/deferred; never independently verified. Unknown/deferred never satisfies required facts. Source: `cms-slice/apps/ten-question/readiness-core.js::question`.

### RC25.V1 · runtime_variant

**Question:** What should that amount include: monthly premiums or total spending?

**Options:** Add an optional budget; No fixed limit; Prefer not to say

**Fields:** `readiness.facts.RC25.value.includes`

**Purpose:** Why we ask: A low plan premium is not the whole cost.

**Applicability / required:** Only the missing child detail/variant of RC25; deduplicate against the parent report. · optional_preference

**Comparison scope:** Optional preference / explanation depth.

**Dependencies:** RC03, RC18. **Stale on change:** coverage.current, relevant_parent_report.

**Evidence:** explicit user report or explicit unknown/deferred; never independently verified. Unknown/deferred never satisfies required facts. Source: `cms-slice/apps/ten-question/readiness-core.js::question`.

## Exact detail controls

These are label/field controls from the registry; internal entity references are not questions.

- `RC02.zip` — Home ZIP (zip); missing relevant detail of the parent question.

- `RC02.county` — Home county and state (text); missing relevant detail of the parent question.

- `RC02.homeStatus` — Permanent-home or moving/seasonal clarification (text); missing relevant detail of the parent question.

- `RC03.year` — Other benefit year (year); missing relevant detail of the parent question.

- `RC05.month` — Part B start month, if known (month); missing relevant detail of the parent question.

- `RC06.ageBand` — Current age range, if known (ageBand); missing relevant detail of the parent question.

- `RC08.eventDate` — Date of the change, if known (date); missing relevant detail of the parent question.

- `RC11.jobEnd` — Job end date, if known (date); missing relevant detail of the parent question.

- `RC11.coverageEnd` — Coverage end date, if known (date); missing relevant detail of the parent question.

- `RC12.gap` — Drug coverage gap, if any (text); missing relevant detail of the parent question.

- `RC15.event` — Relevant change or notice (text); missing relevant detail of the parent question.

- `RC16.start` — Advantage start date (date); missing relevant detail of the parent question.

- `RC16.priorMedigap` — Prior Medigap, if any (text); missing relevant detail of the parent question.

- `RC19.qualification` — Specific qualifying program or plan confirmation (text); missing relevant detail of the parent question.

- `RC20.location` — State or country, if known (text); missing relevant detail of the parent question.

- `RC21.entity` — Listed doctor reference (text); internal reference, not consumer intake.

- `RC21.practice` — Doctor / hospital and practice (text); missing relevant detail of the parent question.

- `RC21.city` — Office city and state (text); missing relevant detail of the parent question.

- `RC22.entity` — Listed medicine reference (text); internal reference, not consumer intake.

- `RC22.name` — Prescription name (text); missing relevant detail of the parent question.

- `RC22.strength` — Strength (text); missing relevant detail of the parent question.

- `RC22.form` — Form, such as tablet or inhaler (text); missing relevant detail of the parent question.

- `RC22.brand` — Brand or generic preference, including no preference (text); missing relevant detail of the parent question.

- `RC23.entity` — Listed medicine reference (text); internal reference, not consumer intake.

- `RC23.quantity` — Quantity (text); missing relevant detail of the parent question.

- `RC23.daysSupply` — Days supply (text); missing relevant detail of the parent question.

- `RC23.pharmacy` — Exact pharmacy and location (text); missing relevant detail of the parent question.

- `RC23.channel` — Retail or mail order (text); missing relevant detail of the parent question.

- `RC23.supply` — Earlier reported supply wording (text); legacy wording, not an additional required field.

- `RC25.amount` — Monthly amount or range, if you want (text); missing relevant detail of the parent question.

- `RC25.includes` — What should that amount include? (text); missing relevant detail of the parent question.

## Non-intake boundaries

- RC29: system missing-data/source capability guard; no customer question can remove it.

- RC30: future final application/transition review; held and excluded from intake.

## Validation status

The 29 source references remain research-only and not domain-approved policy. This mapping supports reported-input preparation, capability-specific fail-closed gates and explicit sample browsing; it does not authorize legal/eligibility conclusions, personal ranking, enrollment or a complete market claim.


## Preserved legacy guide question nodes

The previous guide contract also retains 46 question-form nodes, of which 34 are intake/comparison nodes and the rest concern learning, navigation, consent or operations. They are enumerated here and in `historicalQuestionNodes` in the machine map, are not added to the active 41-primary/child count, and do not become new required intake. Many duplicate baseline/RC semantics. Existing narrow-purpose/optional privacy rules remain; legacy birth/benefit details are not newly collected.

- **A01** · legacy_intake_or_comparison · What would you like help with today? → `guide.fields.intent.goal`, `guide.fields.intent.goalRaw`. Inactive in alternative; not required by current gate.

- **A02** · legacy_intake_or_comparison · Who is this for? → `guide.fields.subject.role`, `guide.fields.subject.displayLabel`. Inactive in alternative; not required by current gate.

- **A02B** · legacy_intake_or_comparison · How would you like us to refer to them? → `guide.fields.subject.displayLabel`. Inactive in alternative; not required by current gate.

- **A03** · legacy_intake_or_comparison · How familiar are you with Medicare? → `guide.fields.knowledge.general`, `guide.fields.presentation.depth`. Inactive in alternative; not required by current gate.

- **A04** · legacy_intake_or_comparison · What do you already know, and what would you like explained? → `guide.fields.drafts.knowledgeRaw`. Inactive in alternative; not required by current gate.

- **A05** · legacy_learning_navigation_consent_or_operation · Would you like to save this guide for your next visit? → `guide.fields.privacy.persistenceChoice`, `guide.fields.privacy.noticeAcknowledgedAt`. Inactive in alternative; not required by current gate.

- **L00** · legacy_learning_navigation_consent_or_operation · What is Medicare? → `guide.fields.knowledge.topics.medicare.seen`, `guide.fields.knowledge.topics.medicare.selfReport`. Inactive in alternative; not required by current gate.

- **L01** · legacy_learning_navigation_consent_or_operation · What would help next? → `guide.fields.intent.learningNext`. Inactive in alternative; not required by current gate.

- **C00** · legacy_intake_or_comparison · Do you have Medicare yet? → `guide.fields.coverage.enrollment`. Inactive in alternative; not required by current gate.

- **C01** · legacy_intake_or_comparison · Would you like help checking what is in place? → `guide.fields.checks.enrollment`. Inactive in alternative; not required by current gate.

- **C02** · legacy_intake_or_comparison · Do you receive Social Security or Railroad Retirement benefits? → `guide.fields.coverage.socialBenefits`. Inactive in alternative; not required by current gate.

- **C03** · legacy_intake_or_comparison · Which coverage do you have now? → `guide.fields.coverage.current`, `guide.fields.intent.change`. Inactive in alternative; not required by current gate.

- **C04** · legacy_intake_or_comparison · What would you like to do with this coverage? → `guide.fields.intent.change`. Inactive in alternative; not required by current gate.

- **C05** · legacy_intake_or_comparison · What birth month and year should we use for age-based timing? → `guide.fields.coverage.birth`. Inactive in alternative; not required by current gate.

- **C06** · legacy_intake_or_comparison · Is the birthday on the first day of the month? → `guide.fields.coverage.birth.firstDay`. Inactive in alternative; not required by current gate.

- **C07** · legacy_intake_or_comparison · Do you know the Part B start month? → `guide.fields.coverage.partBStart`. Inactive in alternative; not required by current gate.

- **J00** · legacy_intake_or_comparison · Does health insurance come from your own or a spouse’s current job? → `guide.fields.coverage.job.status`, `guide.fields.intent.jobTask`. Inactive in alternative; not required by current gate.

- **J01** · legacy_intake_or_comparison · What would help with the job coverage? → `guide.fields.intent.jobTask`. Inactive in alternative; not required by current gate.

- **J02** · legacy_intake_or_comparison · How many employees does the employer have? → `guide.fields.coverage.job.employerSize`. Inactive in alternative; not required by current gate.

- **J03** · legacy_intake_or_comparison · When do employment and health coverage end? → `guide.fields.coverage.job.employmentEnd`, `guide.fields.coverage.job.coverageEnd`. Inactive in alternative; not required by current gate.

- **J04** · legacy_intake_or_comparison · When does the job health coverage end? → `guide.fields.coverage.job.coverageEnd`. Inactive in alternative; not required by current gate.

- **J05** · legacy_intake_or_comparison · Has the current coverage confirmed that its drug coverage is creditable? → `guide.fields.coverage.creditableDrug`. Inactive in alternative; not required by current gate.

- **N00** · legacy_intake_or_comparison · Do you take prescription medicines? → `guide.fields.needs.medicinesStatus`. Inactive in alternative; not required by current gate.

- **N01** · legacy_intake_or_comparison · Would you like to add medicines to the checking list? → `guide.fields.needs.medications`. Inactive in alternative; not required by current gate.

- **N02** · legacy_intake_or_comparison · Is there a pharmacy you would like to check? → `guide.fields.needs.pharmacies`. Inactive in alternative; not required by current gate.

- **N03** · legacy_intake_or_comparison · Which dental, vision or hearing needs should we check? → `guide.fields.needs.extras`. Inactive in alternative; not required by current gate.

- **N04** · legacy_intake_or_comparison · What is most important to you? → `guide.fields.needs.priorities`. Inactive in alternative; not required by current gate.

- **N05** · legacy_intake_or_comparison · If these pull in different directions, which matters most? → `guide.fields.needs.priorityOrder`. Inactive in alternative; not required by current gate.

- **N06** · legacy_intake_or_comparison · Which doctors or hospitals would you like to check? → `guide.fields.needs.providers`. Inactive in alternative; not required by current gate.

- **O00** · legacy_intake_or_comparison · Which plans or options would you like to compare? → `guide.fields.intent.compareKind`, `guide.fields.intent.comparisonMode`. Inactive in alternative; not required by current gate.

- **O01** · legacy_intake_or_comparison · How would you like to explore these options? → `guide.fields.intent.comparisonMode`. Inactive in alternative; not required by current gate.

- **O02** · legacy_intake_or_comparison · Which plans do you have in mind? → `guide.fields.comparison.requestedNames`. Inactive in alternative; not required by current gate.

- **O03** · legacy_intake_or_comparison · Where and which coverage year? → `guide.fields.comparison.scope.zip`, `guide.fields.comparison.scope.county`, `guide.fields.comparison.scope.locationEvidence`, `guide.fields.comparison.scope.year`. Inactive in alternative; not required by current gate.

- **O04B** · legacy_intake_or_comparison · Which county is the home in? → `guide.fields.comparison.scope.county`. Inactive in alternative; not required by current gate.

- **O05** · legacy_intake_or_comparison · Which coverage year are you exploring? → `guide.fields.comparison.scope.year`. Inactive in alternative; not required by current gate.

- **O06B** · legacy_intake_or_comparison · Which exact record did you mean? → `guide.fields.comparison.candidates`. Inactive in alternative; not required by current gate.

- **O10** · legacy_intake_or_comparison · What would you like to keep as your current preference? → `guide.fields.intent.statedPreference`. Inactive in alternative; not required by current gate.

- **H00** · legacy_learning_navigation_consent_or_operation · Would you like help reviewing the next step? → `guide.fields.outcome.handoffIntent`. Inactive in alternative; not required by current gate.

- **X01** · legacy_learning_navigation_consent_or_operation · Did Daylight understand you correctly? → `guide.fields.confirmed_patch`, `guide.fields.history.event`. Inactive in alternative; not required by current gate.

- **X05** · legacy_learning_navigation_consent_or_operation · Resume your saved guide? → `guide.fields.session.active`. Inactive in alternative; not required by current gate.

- **X07** · legacy_learning_navigation_consent_or_operation · Delete this saved guest guide? → `guide.fields.deletion.request`. Inactive in alternative; not required by current gate.

- **X08** · legacy_learning_navigation_consent_or_operation · Save medicine and provider details for another visit? → `guide.fields.privacy.sensitiveChoice`. Inactive in alternative; not required by current gate.

- **E01** · legacy_learning_navigation_consent_or_operation · What would help you next? → No customer profile fields. Inactive in alternative; not required by current gate.

- **E02** · legacy_learning_navigation_consent_or_operation · What would help you next? → No customer profile fields. Inactive in alternative; not required by current gate.

- **E03** · legacy_learning_navigation_consent_or_operation · What would you like to do next? → No customer profile fields. Inactive in alternative; not required by current gate.

- **E04** · legacy_learning_navigation_consent_or_operation · Which next step would help? → No customer profile fields. Inactive in alternative; not required by current gate.
