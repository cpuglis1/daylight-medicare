# Branching node inventory

**Current presentation: D65 appendix at the end supersedes conflicting legacy separate-screen details.**

Design version 1.0 · 2026-10-21. [Master policy](MASTER_DESIGN.md), [wireframes](WIREFRAMES.md), [machine-readable contract](flow-contract.json). These are proposed implementation contracts, not app functionality. Every node inherits G1 and preflight in MASTER_DESIGN §5. Choices stage values; only deliberate Continue/confirmed action advances. System events complete a previously requested operation, not an automatic answer.

## Complete answer transition matrix

| Node | Phase | Wireframe | Answers / events → next |
|---|---|---|---|
| A00 | P1 | W2 | `start` → `A01`; `shortcut` → `A03`; `resume` → `X05` |
| A01 | P1 | W2 | `learn` → `A02`; `compare` → `A02`; `review` → `A02`; `job` → `A02`; `other` → `X01` |
| A02 | P1 | W2 | `self` → `A03`; `someone` → `A02B`; `other` → `X01` |
| A02B | P1 | W3 | `save` → `A03`; `skip` → `A03` |
| A03 | P1 | W2 | `new` → `@after_knowledge`; `some` → `@after_knowledge`; `comfortable` → `@after_knowledge`; `text` → `A04`; `skip` → `@after_knowledge` |
| A04 | P1 | W3 | `propose` → `X01`; `skip` → `@after_knowledge` |
| A05 | P1 | W12 | `save` → `@start_route`; `visit` → `@start_route`; `details` → `X06` |
| L00 | P2 | W5 | `continue` → `@after_lesson`; `know` → `@after_lesson` |
| L01 | P2 | W1 | `parts` → `L02`; `personal` → `C00`; `finish` → `F00`; `other` → `X01` |
| L02 | P2 | W5 | `continue` → `@after_lesson`; `know` → `@after_lesson` |
| L03 | P2 | W5 | `continue` → `@after_lesson`; `know` → `@after_lesson` |
| L04 | P2 | W5 | `continue` → `@after_lesson`; `know` → `@after_lesson` |
| L05 | P2 | W5 | `continue` → `@after_lesson`; `know` → `@after_lesson` |
| L06 | P2 | W5 | `continue` → `@after_lesson`; `know` → `@after_lesson` |
| L07 | P3 | W5 | `continue` → `@after_lesson`; `know` → `@after_lesson` |
| L08 | P3 | W5 | `continue` → `@after_lesson`; `know` → `@after_lesson` |
| L09 | P3 | W5 | `continue` → `@after_lesson`; `know` → `@after_lesson` |
| L10 | P3 | W5 | `continue` → `@after_lesson`; `know` → `@after_lesson` |
| L11 | P3 | W5 | `continue` → `@after_lesson`; `know` → `@after_lesson` |
| L12 | P3 | W5 | `continue` → `@after_lesson`; `know` → `@after_lesson` |
| L13 | P3 | W5 | `continue` → `@after_lesson`; `know` → `@after_lesson` |
| C00 | P2 | W1 | `ab` → `@after_enrollment`; `a` → `@after_enrollment`; `parts_unknown` → `C01`; `no` → `C02`; `unknown` → `C01`; `other` → `X01` |
| C01 | P2 | W1 | `card` → `C01B`; `continue` → `@after_enrollment`; `other` → `X01` |
| C01B | P2 | W1 | `known` → `C00`; `unknown` → `@after_enrollment` |
| C02 | P2 | W1 | `yes` → `@after_enrollment`; `no` → `@after_enrollment`; `unknown` → `@after_enrollment`; `other` → `X01` |
| C03 | P2 | W1 | `original` → `C03`; `medigap` → `C03`; `drug` → `C03`; `advantage` → `C03`; `employer` → `C03`; `va` → `C03`; `medicaid` → `C03`; `none` → `C03`; `unknown` → `C03`; `other` → `X01`; `continue` → `@after_current` |
| C04 | P2 | W1 | `keep` → `@after_change`; `replace` → `@after_change`; `add` → `@after_change`; `unknown` → `@after_change`; `other` → `X01` |
| C05 | P2 | W3 | `date` → `C06`; `unknown` → `@after_timing`; `skip` → `@after_timing` |
| C06 | P2 | W1 | `yes` → `@after_timing`; `no` → `@after_timing`; `unknown` → `@after_timing` |
| C07 | P2 | W3 | `date` → `@after_part_b`; `unknown` → `@after_part_b`; `not_started` → `@after_part_b`; `skip` → `@after_part_b` |
| J00 | P2 | W1 | `active` → `J01`; `ended` → `J01`; `none` → `@after_job`; `unknown` → `@after_job`; `other` → `X01` |
| J01 | P2 | W1 | `prepare` → `J02`; `compare` → `J02`; `unknown` → `J02`; `other` → `X01` |
| J02 | P2 | W1 | `large` → `J03`; `small` → `J03`; `unknown` → `J03`; `other` → `X01` |
| J03 | P2 | W3 | `date` → `J04`; `unknown` → `J04`; `ongoing` → `J04` |
| J04 | P2 | W3 | `date` → `J05`; `unknown` → `J05`; `ongoing` → `J05` |
| J05 | P2 | W1 | `yes` → `@after_transition`; `no` → `@after_transition`; `unknown` → `@after_transition`; `none` → `@after_transition`; `other` → `X01` |
| N00 | P2 | W1 | `yes` → `N01`; `no` → `@after_medicines`; `unknown` → `N01`; `other` → `X01` |
| N01 | P2 | W3 | `save` → `N02`; `skip` → `N02` |
| N02 | P2 | W3 | `save` → `@after_medicines`; `skip` → `@after_medicines`; `unknown` → `@after_medicines` |
| N03 | P2 | W1 | `dental` → `N03`; `vision` → `N03`; `hearing` → `N03`; `none` → `N03`; `unknown` → `N03`; `other` → `X01`; `continue` → `N04` |
| N04 | P2 | W1 | `doctors` → `N04`; `travel` → `N04`; `premium` → `N04`; `bills` → `N04`; `drugs` → `N04`; `unknown` → `N04`; `other` → `X01`; `continue` → `@after_priorities` |
| N05 | P2 | W1 | `dynamic` → `@after_priority_order`; `equal` → `@after_priority_order`; `unknown` → `@after_priority_order` |
| N06 | P2 | W3 | `save` → `@after_providers`; `skip` → `@after_providers` |
| O00 | P3 | W1 | `advantage` → `O01`; `medigap` → `L12`; `drugs` → `O01`; `named` → `O02`; `difference` → `L10`; `other` → `X01` |
| O01 | P3 | W1 | `browse` → `O03`; `personal` → `@personal_entry`; `unknown` → `O03` |
| O02 | P3 | W3 | `search` → `O03`; `unknown` → `O00` |
| O03 | P3 | W1 | `valid` → `O04`; `unknown` → `O05`; `skip` → `O05` |
| O04 | P3 | W1 | `unique` → `O05`; `multiple` → `O04B`; `missing` → `O04B`; `error` → `O04B` |
| O04B | P3 | W1 | `dynamic` → `O05`; `different` → `O05`; `unknown` → `O05`; `edit` → `O03` |
| O05 | P3 | W1 | `supported` → `O06`; `current` → `X04`; `unknown` → `X04` |
| O06 | P3 | W11 | `accepted` → `O07`; `empty` → `X04`; `pending` → `X04`; `error` → `X02`; `ambiguous_name` → `O06B` |
| O06B | P3 | W1 | `dynamic` → `O07`; `unknown` → `O07`; `edit` → `O02` |
| O07 | P3 | W9 | `save` → `O07`; `filter` → `O07`; `details` → `O08`; `compare` → `O09`; `personal` → `@personal_entry`; `continue` → `F00` |
| O08 | P3 | W9 | `save` → `O08`; `back` → `O07`; `continue` → `O07` |
| O09 | P3 | W10 | `edit` → `O07`; `choose` → `O10`; `continue` → `F00` |
| O10 | P3 | W10 | `candidate` → `F00`; `keep` → `F00`; `undecided` → `F00`; `checks` → `F00` |
| O11 | P3 | W11 | `rights` → `C07`; `prepare` → `F01`; `other_options` → `O00`; `continue` → `F00` |
| F00 | P4 | W13 | `prepare` → `F01`; `learning` → `L01`; `options` → `O07`; `finish` → `F03` |
| F01 | P4 | W13 | `edit` → `F01`; `copy` → `F01`; `print` → `F02`; `handoff` → `H00`; `continue` → `F00` |
| F02 | P4 | W13 | `print` → `F02`; `return` → `F00` |
| F03 | P4 | W12 | `save` → `F03`; `forget` → `X06`; `delete` → `X07`; `return` → `F00` |
| H00 | P4 | W13 | `official` → `F00`; `prepare` → `F01`; `request` → `H01`; `skip` → `F00` |
| H01 | P4 | W13 | `approve` → `H02`; `edit` → `H01`; `cancel` → `F00` |
| H02 | P4 | W13 | `receipt` → `F00`; `pending` → `H02`; `failed` → `H01`; `uncertain` → `X03`; `cancel` → `H02` |
| X01 | preserve | W4 | `accept` → `@confirmed_return`; `edit` → `X01`; `unknown` → `@unknown_return`; `cancel` → `@origin` |
| X02 | preserve | W11 | `retry` → `@origin`; `local` → `@safe_local`; `return` → `@origin` |
| X03 | preserve | W11 | `reload` → `@origin`; `merge` → `X01`; `discard` → `@origin` |
| X04 | preserve | W11 | `edit` → `O00`; `official` → `F00`; `prepare` → `F01`; `learn` → `L01` |
| X05 | P1 | W12 | `resume` → `@resume`; `private` → `A01`; `manage` → `X06` |
| X06 | preserve | W12 | `return` → `@origin`; `visit` → `@origin`; `sensitive` → `X08`; `forget` → `X09`; `delete` → `X07` |
| X07 | preserve | W12 | `delete` → `X09`; `cancel` → `@origin` |
| X08 | preserve | W12 | `save` → `@origin`; `visit` → `@origin`; `remove` → `X07` |
| X09 | P1 | W12 | `new` → `A00` |
| X10 | preserve | W7/W8 | `question` → `X10`; `followup` → `X10`; `propose` → `X01`; `return` → `@origin` |

## Ordered resolver rules

First matching condition wins; `else` is mandatory. Aliases/predicates/return tokens are defined in JSON and master §5; unknown/missing never become true by inference. Lesson queues are server-created, bounded and cycle-free.

### @after_knowledge

- `privacy.choice_not_recorded` → `A05`
- `else` → `@start_route`

### @start_route

- `personalReview=true` → `@personal_entry`
- `goal=learn` → `L00`
- `goal=compare` → `O00`
- `goal IN unresolved,unanswered` → `L00`
- `else` → `@personal_entry`

### @personal_entry

- `recipient=unanswered` → `A02`
- `personalContextReady=true` → `O03`
- `novice_requires_parts` → `L00`
- `else` → `C00`

### @after_parts

- `lessonReturn=set` → `@lesson_return`
- `goal=learn AND personalReview=false` → `L05`
- `else` → `C00`

### @after_drug_lesson

- `lessonReturn=set` → `@lesson_return`
- `goal=learn AND personalReview=false` → `L06`
- `else` → `N00`

### @after_extras_lesson

- `lessonReturn=set` → `@lesson_return`
- `goal=learn AND personalReview=false` → `L07`
- `else` → `N03`

### @after_cost_lesson

- `lessonReturn=set` → `@lesson_return`
- `goal=learn AND personalReview=false` → `L10`
- `else` → `O00`

### @after_routes_lesson

- `lessonReturn=set` → `@lesson_return`
- `compareKind=difference` → `O00`
- `goal=learn AND personalReview=false` → `L01`
- `else` → `O00`

### @after_supplement_lesson

- `lessonReturn=set` → `@lesson_return`
- `else` → `O11`

### @after_enrollment

- `goal=job` → `J00`
- `enrollment IN ab,parts_unknown,b_only` → `C03`
- `else` → `J00`

### @after_current

- `goal=job` → `J00`
- `goal=review` → `C04`
- `else` → `N00`

### @after_change

- `change=keep` → `F00`
- `change IN add,replace` → `O00`
- `else` → `N00`

### @after_job

- `goal=job` → `J03`
- `dateTask=needed` → `C05`
- `else` → `N00`

### @after_timing

- `partBDateTask=needed` → `C07`
- `else` → `N00`

### @after_part_b

- `compareKind=medigap` → `O11`
- `else` → `N00`

### @after_transition

- `jobTask IN prepare,unknown OR jobTask=unanswered` → `F00`
- `else` → `N00`

### @after_medicines

- `needsCollection=optional_declined` → `O00`
- `else` → `N03`

### @after_priorities

- `priorityCount>1` → `N05`
- `else` → `@after_priority_order`

### @after_priority_order

- `priority IN doctors,travel` → `N06`
- `novice_requires_costs` → `L07`
- `else` → `O00`

### @after_providers

- `novice_requires_costs` → `L07`
- `else` → `O00`

### @confirmed_return

- `proposal.context=knowledge` → `@after_knowledge`
- `proposal.context=goal AND recipient=unanswered` → `A02`
- `else` → `@confirmed_dispatch`

### @unknown_return

- `proposal.context=goal AND privacy.choice_not_recorded` → `A05`
- `proposal.context=goal` → `L00`
- `proposal.context=knowledge` → `@after_knowledge`
- `else` → `@confirmed_dispatch`

### @origin

- `else` → `TOKEN:origin`

### @lesson_return

- `else` → `TOKEN:lessonReturn`

### @confirmed_dispatch

- `else` → `TOKEN:confirmedDispatch`

### @safe_local

- `else` → `TOKEN:safeLocal`

### @resume

- `else` → `TOKEN:resume`

### @after_lesson

- `lessonQueue=remaining` → `TOKEN:nextLesson`
- `lessonReturn=set` → `@lesson_return`
- `else` → `TOKEN:lessonDefault`

## Node specifications

### A00 · Introduce the agent and establish an entry intention.

**Phase / surface / wireframe:** P1 / arrival / W2. **Prerequisite:** authenticated_guest_or_ephemeral.
**Required vocabulary:** contextual inline terms; no forced full lesson. Preflight and G1 apply.

**Exact proposed question:** Your coverage, plain as day
**Why asked / microcopy:** Daylight is an AI assistant for learning, reviewing published information, and preparing next steps. You stay in control.

| Answer / event | Visible proposed label | Confirmed next target |
|---|---|---|
| `start` | Get started | `A01` |
| `shortcut` | Skip explanations and compare published plans | `A03` |
| `resume` | Resume my saved guide | `X05` |

**Reads:** session.status. **Allowed writes:** intent.entryMode, presentation.depth.
**Answer effects:** `start`: set entryMode=guided; `shortcut`: set entryMode=shortcut, goal=compare, presentation.depth=concise; knowledge stays unanswered; `resume`: read authenticated session only.
**Agent responsibility:** Use the current task and confirmed profile to explain why this matters. A typed opening can propose goal and recipient together through X01. Do not expose the full insurance picture on arrival. Never commit an extracted fact or change the route without confirmation.
**Validation:** Choose one explicit answer; no fresh defaults.
**Picture delta:** `none`; add only introduced concept(s), never change enrollment facts. **Progress:** P1 (preserve means unchanged phase). **Help:** A00 plus literal current task and permitted minimum context.
**Requirement IDs:** D03, D04, D05, D38, D40, D49.

**Acceptance:**
- A00-A: each listed answer has exactly one defined next target after Continue.
- A00-B: Back, edit, help return, unknown and failed-save behavior obey G1; original text and prior confirmed entries survive.
- A00-C: only declared profile writes occur; picture changes obey concept prerequisites.
- A00-D: Choose one explicit answer; no fresh defaults.
- A00-E: open X10 then Return/Escape restores this node’s values, draft, visible question and reading position.

### A01 · Establish the visit goal.

**Phase / surface / wireframe:** P1 / single_choice / W2. **Prerequisite:** authenticated_guest_or_ephemeral.
**Required vocabulary:** contextual inline terms; no forced full lesson. Preflight and G1 apply.

**Exact proposed question:** What would you like help with today?
**Why asked / microcopy:** Your goal helps Daylight choose useful explanations and questions.

| Answer / event | Visible proposed label | Confirmed next target |
|---|---|---|
| `learn` | Understand Medicare | `A02` |
| `compare` | Compare plans | `A02` |
| `review` | Review or change my coverage | `A02` |
| `job` | My job coverage is ending | `A02` |
| `other` | Something else | `X01` |

**Reads:** intent.goal. **Allowed writes:** intent.goal, intent.goalRaw.
**Answer effects:** `*`: stage intent.goal from explicit enum; other retains raw and proposes, no confirmed mutation.
**Agent responsibility:** Use the current task and confirmed profile to explain why this matters. Retain the four established goal cards. Something else is a separate text answer below them, not a fifth equally prominent route. Free text may suggest any of the four or an unresolved support goal. Never commit an extracted fact or change the route without confirmation.
**Validation:** Choose one explicit answer; no fresh defaults.
**Picture delta:** `none`; add only introduced concept(s), never change enrollment facts. **Progress:** P1 (preserve means unchanged phase). **Help:** A01 plus literal current task and permitted minimum context.
**Requirement IDs:** D41, D49, D52.

**Acceptance:**
- A01-A: each listed answer has exactly one defined next target after Continue.
- A01-B: Back, edit, help return, unknown and failed-save behavior obey G1; original text and prior confirmed entries survive.
- A01-C: only declared profile writes occur; picture changes obey concept prerequisites.
- A01-D: Choose one explicit answer; no fresh defaults.
- A01-E: open X10 then Return/Escape restores this node’s values, draft, visible question and reading position.

### A02 · Identify whose facts are being entered.

**Phase / surface / wireframe:** P1 / single_choice / W2. **Prerequisite:** authenticated_guest_or_ephemeral.
**Required vocabulary:** contextual inline terms; no forced full lesson. Preflight and G1 apply.

**Exact proposed question:** Who is this for?
**Why asked / microcopy:** This keeps questions and saved details about the person receiving coverage.

| Answer / event | Visible proposed label | Confirmed next target |
|---|---|---|
| `self` | Me | `A03` |
| `someone` | Someone I am helping | `A02B` |
| `other` | Something else | `X01` |

**Reads:** intent.goal. **Allowed writes:** subject.role.
**Answer effects:** `*`: Commit only declared fields from the explicit reviewed answer, with typed envelope and original text; unknown/skipped status remains distinct. Non-answer actions mutate only their named control scope..
**Agent responsibility:** Use the current task and confirmed profile to explain why this matters. Never interpret caregiver status as legal representative authority. Never commit an extracted fact or change the route without confirmation.
**Validation:** Choose one explicit answer; no fresh defaults.
**Picture delta:** `none`; add only introduced concept(s), never change enrollment facts. **Progress:** P1 (preserve means unchanged phase). **Help:** A02 plus literal current task and permitted minimum context.
**Requirement IDs:** D06, D08, D12, D21, D49, D50.

**Acceptance:**
- A02-A: each listed answer has exactly one defined next target after Continue.
- A02-B: Back, edit, help return, unknown and failed-save behavior obey G1; original text and prior confirmed entries survive.
- A02-C: only declared profile writes occur; picture changes obey concept prerequisites.
- A02-D: Choose one explicit answer; no fresh defaults.
- A02-E: open X10 then Return/Escape restores this node’s values, draft, visible question and reading position.

### A02B · Set respectful caregiver wording without identifiers.

**Phase / surface / wireframe:** P1 / optional_text / W3. **Prerequisite:** authenticated_guest_or_ephemeral.
**Required vocabulary:** contextual inline terms; no forced full lesson. Preflight and G1 apply.

**Exact proposed question:** How would you like us to refer to them?
**Why asked / microcopy:** A relationship or first name is optional. No Medicare or Social Security number is needed.

| Answer / event | Visible proposed label | Confirmed next target |
|---|---|---|
| `save` | Use this wording | `A03` |
| `skip` | Continue without a name | `A03` |

**Reads:** subject.role. **Allowed writes:** subject.displayLabel.
**Answer effects:** `*`: Commit only declared fields from the explicit reviewed answer, with typed envelope and original text; unknown/skipped status remains distinct. Non-answer actions mutate only their named control scope..
**Agent responsibility:** Use the current task and confirmed profile to explain why this matters. Default wording is “the person you are helping”; a name is not an account. Never commit an extracted fact or change the route without confirmation.
**Validation:** Optional plain text 0–80 characters; reject markup; warn on likely ID number; do not require relationship.
**Picture delta:** `none`; add only introduced concept(s), never change enrollment facts. **Progress:** P1 (preserve means unchanged phase). **Help:** A02B plus literal current task and permitted minimum context.
**Requirement IDs:** D06, D08, D12, D21, D49, D50.

**Acceptance:**
- A02B-A: each listed answer has exactly one defined next target after Continue.
- A02B-B: Back, edit, help return, unknown and failed-save behavior obey G1; original text and prior confirmed entries survive.
- A02B-C: only declared profile writes occur; picture changes obey concept prerequisites.
- A02B-D: Optional plain text 0–80 characters; reject markup; warn on likely ID number; do not require relationship.
- A02B-E: open X10 then Return/Escape restores this node’s values, draft, visible question and reading position.

### A03 · Set teaching depth independently of the goal.

**Phase / surface / wireframe:** P1 / knowledge / W2. **Prerequisite:** authenticated_guest_or_ephemeral.
**Required vocabulary:** contextual inline terms; no forced full lesson. Preflight and G1 apply.

**Exact proposed question:** How familiar are you with Medicare?
**Why asked / microcopy:** This changes how much we explain. It does not affect which facts need checking.

| Answer / event | Visible proposed label | Confirmed next target |
|---|---|---|
| `new` | New to Medicare | `@after_knowledge` |
| `some` | Know some basics | `@after_knowledge` |
| `comfortable` | Comfortable with the basics | `@after_knowledge` |
| `text` | I would rather explain in my own words | `A04` |
| `skip` | Skip this for now | `@after_knowledge` |

**Reads:** intent.entryMode, intent.goal, knowledge.general. **Allowed writes:** knowledge.general, presentation.depth.
**Answer effects:** `new`: knowledge.general=new; depth=full; `some`: knowledge.general=some; depth=contextual; `comfortable`: knowledge.general=comfortable; depth=concise; `text`: stage raw description only; `skip`: knowledge.general=skipped; no expertise inference; retain explicit shortcut concise preference.
**Agent responsibility:** Use the current task and confirmed profile to explain why this matters. The shortcut only expresses a wish for concise teaching. Its Skip choice leaves knowledge unknown. No quiz or competency judgment. Never commit an extracted fact or change the route without confirmation.
**Validation:** Choose one explicit answer; no fresh defaults.
**Picture delta:** `none`; add only introduced concept(s), never change enrollment facts. **Progress:** P1 (preserve means unchanged phase). **Help:** A03 plus literal current task and permitted minimum context.
**Requirement IDs:** D31, D49, D50.

**Acceptance:**
- A03-A: each listed answer has exactly one defined next target after Continue.
- A03-B: Back, edit, help return, unknown and failed-save behavior obey G1; original text and prior confirmed entries survive.
- A03-C: only declared profile writes occur; picture changes obey concept prerequisites.
- A03-D: Choose one explicit answer; no fresh defaults.
- A03-E: open X10 then Return/Escape restores this node’s values, draft, visible question and reading position.

### A04 · Interpret a nuanced knowledge description.

**Phase / surface / wireframe:** P1 / free_text / W3. **Prerequisite:** authenticated_guest_or_ephemeral.
**Required vocabulary:** contextual inline terms; no forced full lesson. Preflight and G1 apply.

**Exact proposed question:** What do you already know, and what would you like explained?
**Why asked / microcopy:** You can describe your starting point in your own words.

| Answer / event | Visible proposed label | Confirmed next target |
|---|---|---|
| `propose` | Review Daylight’s interpretation | `X01` |
| `skip` | Keep knowledge unknown | `@after_knowledge` |

**Reads:** knowledge.general, intent.goal. **Allowed writes:** drafts.knowledgeRaw.
**Answer effects:** `*`: Commit only declared fields from the explicit reviewed answer, with typed envelope and original text; unknown/skipped status remains distinct. Non-answer actions mutate only their named control scope..
**Agent responsibility:** Use the current task and confirmed profile to explain why this matters. Propose new/some/comfortable/unknown plus per-topic preferences; retain verbatim text and ask confirmation. No insurance fact follows from knowledge. Never commit an extracted fact or change the route without confirmation.
**Validation:** 0–1200 characters, multiline; empty text supports Skip only.
**Picture delta:** `none`; add only introduced concept(s), never change enrollment facts. **Progress:** P1 (preserve means unchanged phase). **Help:** A04 plus literal current task and permitted minimum context.
**Requirement IDs:** D06, D08, D12, D21, D49, D50.

**Acceptance:**
- A04-A: each listed answer has exactly one defined next target after Continue.
- A04-B: Back, edit, help return, unknown and failed-save behavior obey G1; original text and prior confirmed entries survive.
- A04-C: only declared profile writes occur; picture changes obey concept prerequisites.
- A04-D: 0–1200 characters, multiline; empty text supports Skip only.
- A04-E: open X10 then Return/Escape restores this node’s values, draft, visible question and reading position.

### A05 · Choose a storage mode before durable writes.

**Phase / surface / wireframe:** P1 / privacy_notice / W12. **Prerequisite:** authenticated_guest_or_ephemeral.
**Required vocabulary:** contextual inline terms; no forced full lesson. Preflight and G1 apply.

**Exact proposed question:** Would you like to save this guide for your next visit?
**Why asked / microcopy:** Daylight can save a guest profile on its servers without an account. This browser can reopen it. Anyone using this browser may be able to access it.

| Answer / event | Visible proposed label | Confirmed next target |
|---|---|---|
| `save` | Save a guest guide on this browser | `@start_route` |
| `visit` | Use only for this visit | `@start_route` |
| `details` | Review what is saved | `X06` |

**Reads:** privacy.noticeVersion, session.status. **Allowed writes:** privacy.persistenceChoice, privacy.noticeAcknowledgedAt.
**Answer effects:** `save`: record guest_save acknowledgment only after approved notice; enable eligible durable fields; `visit`: record visit_only; do not persist profile content; `details`: read privacy panel; no preference change.
**Agent responsibility:** Use the current task and confirmed profile to explain why this matters. Show the actual approved retention period, deletion controls and shared-device warning. Until those exist, mark persistence unavailable. Never commit an extracted fact or change the route without confirmation.
**Validation:** No preselection. Save requires the approved retention notice and available secure guest service. If policy/service unavailable offer visit-only, not fake Saved.
**Picture delta:** `none`; add only introduced concept(s), never change enrollment facts. **Progress:** P1 (preserve means unchanged phase). **Help:** A05 plus literal current task and permitted minimum context.
**Requirement IDs:** D17, D23, D53, D54.

**Acceptance:**
- A05-A: each listed answer has exactly one defined next target after Continue.
- A05-B: Back, edit, help return, unknown and failed-save behavior obey G1; original text and prior confirmed entries survive.
- A05-C: only declared profile writes occur; picture changes obey concept prerequisites.
- A05-D: No preselection. Save requires the approved retention notice and available secure guest service. If policy/service unavailable offer visit-only, not fake Saved.
- A05-E: open X10 then Return/Escape restores this node’s values, draft, visible question and reading position.

### L00 · Introduce Medicare without the alphabet of products.

**Phase / surface / wireframe:** P2 / lesson / W5. **Prerequisite:** authenticated_guest_or_ephemeral.
**Required vocabulary:** contextual inline terms; no forced full lesson. Preflight and G1 apply.

**Exact proposed question:** What is Medicare?
**Why asked / microcopy:** This gives us a common starting point before discussing the person’s situation.

| Answer / event | Visible proposed label | Confirmed next target |
|---|---|---|
| `continue` | Continue | `@after_lesson` |
| `know` | I know this | `@after_lesson` |

**Reads:** knowledge.general. **Allowed writes:** knowledge.topics.medicare.seen, knowledge.topics.medicare.selfReport.
**Answer effects:** `*`: Continue marks seen only; I know records explicit topic familiarity; both obey lesson return queue..
**Agent responsibility:** Use the current task and confirmed profile to explain why this matters. Reviewed lesson: federal health insurance, mainly for 65+ and some younger people; eligibility still needs checking. Continue means seen, not understood. Never commit an extracted fact or change the route without confirmation.
**Validation:** Choose one explicit answer; no fresh defaults.
**Picture delta:** `add:medicare`; add only introduced concept(s), never change enrollment facts. **Progress:** P2 (preserve means unchanged phase). **Help:** L00 plus literal current task and permitted minimum context.
**Requirement IDs:** D29, D30, D50, D55.

**Acceptance:**
- L00-A: each listed answer has exactly one defined next target after Continue.
- L00-B: Back, edit, help return, unknown and failed-save behavior obey G1; original text and prior confirmed entries survive.
- L00-C: only declared profile writes occur; picture changes obey concept prerequisites.
- L00-D: Choose one explicit answer; no fresh defaults.
- L00-E: open X10 then Return/Escape restores this node’s values, draft, visible question and reading position.

### L01 · Let education be useful without mandatory intake.

**Phase / surface / wireframe:** P2 / learning_intent / W1. **Prerequisite:** authenticated_guest_or_ephemeral.
**Required vocabulary:** contextual inline terms; no forced full lesson. Preflight and G1 apply.

**Exact proposed question:** What would help next?
**Why asked / microcopy:** You can keep learning without entering personal coverage details.

| Answer / event | Visible proposed label | Confirmed next target |
|---|---|---|
| `parts` | How the Medicare parts fit together | `L02` |
| `personal` | Connect this to my situation | `C00` |
| `finish` | Keep what I have learned and see next steps | `F00` |
| `other` | Something else | `X01` |

**Reads:** intent.goal, knowledge.topics. **Allowed writes:** intent.learningNext.
**Answer effects:** `*`: Commit only declared fields from the explicit reviewed answer, with typed envelope and original text; unknown/skipped status remains distinct. Non-answer actions mutate only their named control scope..
**Agent responsibility:** Use the current task and confirmed profile to explain why this matters. Agent can suggest a relevant eligible topic based on the stated question; the person confirms the next topic. Never commit an extracted fact or change the route without confirmation.
**Validation:** Choose one explicit answer; no fresh defaults.
**Picture delta:** `none`; add only introduced concept(s), never change enrollment facts. **Progress:** P2 (preserve means unchanged phase). **Help:** L01 plus literal current task and permitted minimum context.
**Requirement IDs:** D06, D08, D12, D21, D49, D50.

**Acceptance:**
- L01-A: each listed answer has exactly one defined next target after Continue.
- L01-B: Back, edit, help return, unknown and failed-save behavior obey G1; original text and prior confirmed entries survive.
- L01-C: only declared profile writes occur; picture changes obey concept prerequisites.
- L01-D: Choose one explicit answer; no fresh defaults.
- L01-E: open X10 then Return/Escape restores this node’s values, draft, visible question and reading position.

### L02 · Introduce hospital insurance.

**Phase / surface / wireframe:** P2 / lesson / W5. **Prerequisite:** concept:medicare.
**Required vocabulary:** contextual inline terms; no forced full lesson. Preflight and G1 apply.

**Exact proposed question:** Part A: hospital care
**Why asked / microcopy:** We introduce one piece at a time so the picture stays readable.

| Answer / event | Visible proposed label | Confirmed next target |
|---|---|---|
| `continue` | Continue | `@after_lesson` |
| `know` | I know this | `@after_lesson` |

**Reads:** knowledge.topics.medicare. **Allowed writes:** knowledge.topics.part_a.seen, knowledge.topics.part_a.selfReport.
**Answer effects:** `*`: Continue marks seen only; I know records explicit topic familiarity; both obey lesson return queue..
**Agent responsibility:** Use the current task and confirmed profile to explain why this matters. Explain hospital insurance with reviewed examples, not a guarantee that all care is paid. Never commit an extracted fact or change the route without confirmation.
**Validation:** Choose one explicit answer; no fresh defaults.
**Picture delta:** `add:part_a`; add only introduced concept(s), never change enrollment facts. **Progress:** P2 (preserve means unchanged phase). **Help:** L02 plus literal current task and permitted minimum context.
**Requirement IDs:** D06, D08, D12, D21, D49, D50.

**Acceptance:**
- L02-A: each listed answer has exactly one defined next target after Continue.
- L02-B: Back, edit, help return, unknown and failed-save behavior obey G1; original text and prior confirmed entries survive.
- L02-C: only declared profile writes occur; picture changes obey concept prerequisites.
- L02-D: Choose one explicit answer; no fresh defaults.
- L02-E: open X10 then Return/Escape restores this node’s values, draft, visible question and reading position.

### L03 · Introduce medical insurance.

**Phase / surface / wireframe:** P2 / lesson / W5. **Prerequisite:** concept:part_a.
**Required vocabulary:** contextual inline terms; no forced full lesson. Preflight and G1 apply.

**Exact proposed question:** Part B: medical care
**Why asked / microcopy:** This is a separate coverage piece for services such as doctors and outpatient care.

| Answer / event | Visible proposed label | Confirmed next target |
|---|---|---|
| `continue` | Continue | `@after_lesson` |
| `know` | I know this | `@after_lesson` |

**Reads:** knowledge.topics.part_a. **Allowed writes:** knowledge.topics.part_b.seen, knowledge.topics.part_b.selfReport.
**Answer effects:** `*`: Continue marks seen only; I know records explicit topic familiarity; both obey lesson return queue..
**Agent responsibility:** Use the current task and confirmed profile to explain why this matters.  Never commit an extracted fact or change the route without confirmation.
**Validation:** Choose one explicit answer; no fresh defaults.
**Picture delta:** `add:part_b`; add only introduced concept(s), never change enrollment facts. **Progress:** P2 (preserve means unchanged phase). **Help:** L03 plus literal current task and permitted minimum context.
**Requirement IDs:** D06, D08, D12, D21, D49, D50.

**Acceptance:**
- L03-A: each listed answer has exactly one defined next target after Continue.
- L03-B: Back, edit, help return, unknown and failed-save behavior obey G1; original text and prior confirmed entries survive.
- L03-C: only declared profile writes occur; picture changes obey concept prerequisites.
- L03-D: Choose one explicit answer; no fresh defaults.
- L03-E: open X10 then Return/Escape restores this node’s values, draft, visible question and reading position.

### L04 · Name the relationship between the two parts.

**Phase / surface / wireframe:** P2 / lesson / W5. **Prerequisite:** concept:part_b.
**Required vocabulary:** contextual inline terms; no forced full lesson. Preflight and G1 apply.

**Exact proposed question:** Parts A and B together: Original Medicare
**Why asked / microcopy:** Knowing this name will help explain the two coverage routes later.

| Answer / event | Visible proposed label | Confirmed next target |
|---|---|---|
| `continue` | Continue | `@after_lesson` |
| `know` | I know this | `@after_lesson` |

**Reads:** flow.lessonReturn, knowledge.topics.part_b. **Allowed writes:** knowledge.topics.original.seen, knowledge.topics.original.selfReport.
**Answer effects:** `*`: Continue marks seen only; I know records explicit topic familiarity; both obey lesson return queue..
**Agent responsibility:** Use the current task and confirmed profile to explain why this matters. Never change reported enrollment because the picture shows conceptual A/B blocks. Never commit an extracted fact or change the route without confirmation.
**Validation:** Choose one explicit answer; no fresh defaults.
**Picture delta:** `connect:original`; add only introduced concept(s), never change enrollment facts. **Progress:** P2 (preserve means unchanged phase). **Help:** L04 plus literal current task and permitted minimum context.
**Requirement IDs:** D06, D08, D12, D21, D49, D50.

**Acceptance:**
- L04-A: each listed answer has exactly one defined next target after Continue.
- L04-B: Back, edit, help return, unknown and failed-save behavior obey G1; original text and prior confirmed entries survive.
- L04-C: only declared profile writes occur; picture changes obey concept prerequisites.
- L04-D: Choose one explicit answer; no fresh defaults.
- L04-E: open X10 then Return/Escape restores this node’s values, draft, visible question and reading position.

### L05 · Introduce prescription coverage before medicine questions.

**Phase / surface / wireframe:** P2 / lesson / W5. **Prerequisite:** concept:original.
**Required vocabulary:** contextual inline terms; no forced full lesson. Preflight and G1 apply.

**Exact proposed question:** Part D: prescription drug coverage
**Why asked / microcopy:** Medicine needs help us identify what still needs checking against a specific plan.

| Answer / event | Visible proposed label | Confirmed next target |
|---|---|---|
| `continue` | Continue | `@after_lesson` |
| `know` | I know this | `@after_lesson` |

**Reads:** flow.lessonReturn, knowledge.topics.original. **Allowed writes:** knowledge.topics.drugs.seen, knowledge.topics.drugs.selfReport.
**Answer effects:** `*`: Continue marks seen only; I know records explicit topic familiarity; both obey lesson return queue..
**Agent responsibility:** Use the current task and confirmed profile to explain why this matters. Mention separate drug plans now; the relationship to Advantage is explained when that route is introduced. No personal price promises. Never commit an extracted fact or change the route without confirmation.
**Validation:** Choose one explicit answer; no fresh defaults.
**Picture delta:** `add:drugs`; add only introduced concept(s), never change enrollment facts. **Progress:** P2 (preserve means unchanged phase). **Help:** L05 plus literal current task and permitted minimum context.
**Requirement IDs:** D06, D08, D12, D21, D49, D50.

**Acceptance:**
- L05-A: each listed answer has exactly one defined next target after Continue.
- L05-B: Back, edit, help return, unknown and failed-save behavior obey G1; original text and prior confirmed entries survive.
- L05-C: only declared profile writes occur; picture changes obey concept prerequisites.
- L05-D: Choose one explicit answer; no fresh defaults.
- L05-E: open X10 then Return/Escape restores this node’s values, draft, visible question and reading position.

### L06 · Explain routine benefit needs without implying a match.

**Phase / surface / wireframe:** P2 / lesson / W5. **Prerequisite:** concept:original.
**Required vocabulary:** contextual inline terms; no forced full lesson. Preflight and G1 apply.

**Exact proposed question:** Routine dental, vision and hearing need a separate check
**Why asked / microcopy:** Recording a need does not establish that a plan covers the treatment or provider.

| Answer / event | Visible proposed label | Confirmed next target |
|---|---|---|
| `continue` | Continue | `@after_lesson` |
| `know` | I know this | `@after_lesson` |

**Reads:** flow.lessonReturn, knowledge.topics.original. **Allowed writes:** knowledge.topics.extras.seen, knowledge.topics.extras.selfReport.
**Answer effects:** `*`: Continue marks seen only; I know records explicit topic familiarity; both obey lesson return queue..
**Agent responsibility:** Use the current task and confirmed profile to explain why this matters.  Never commit an extracted fact or change the route without confirmation.
**Validation:** Choose one explicit answer; no fresh defaults.
**Picture delta:** `add:extras`; add only introduced concept(s), never change enrollment facts. **Progress:** P2 (preserve means unchanged phase). **Help:** L06 plus literal current task and permitted minimum context.
**Requirement IDs:** D06, D08, D12, D21, D49, D50.

**Acceptance:**
- L06-A: each listed answer has exactly one defined next target after Continue.
- L06-B: Back, edit, help return, unknown and failed-save behavior obey G1; original text and prior confirmed entries survive.
- L06-C: only declared profile writes occur; picture changes obey concept prerequisites.
- L06-D: Choose one explicit answer; no fresh defaults.
- L06-E: open X10 then Return/Escape restores this node’s values, draft, visible question and reading position.

### L07 · Explain a monthly premium.

**Phase / surface / wireframe:** P3 / lesson / W5. **Prerequisite:** concept:original.
**Required vocabulary:** contextual inline terms; no forced full lesson. Preflight and G1 apply.

**Exact proposed question:** A premium is what you pay each month
**Why asked / microcopy:** We separate regular payments from costs when you receive care.

| Answer / event | Visible proposed label | Confirmed next target |
|---|---|---|
| `continue` | Continue | `@after_lesson` |
| `know` | I know this | `@after_lesson` |

**Reads:** knowledge.topics.original. **Allowed writes:** knowledge.topics.premium.seen, knowledge.topics.premium.selfReport.
**Answer effects:** `*`: Continue marks seen only; I know records explicit topic familiarity; both obey lesson return queue..
**Agent responsibility:** Use the current task and confirmed profile to explain why this matters. Use no annual amount unless supplied by current accepted evidence. Never commit an extracted fact or change the route without confirmation.
**Validation:** Choose one explicit answer; no fresh defaults.
**Picture delta:** `add:premium`; add only introduced concept(s), never change enrollment facts. **Progress:** P3 (preserve means unchanged phase). **Help:** L07 plus literal current task and permitted minimum context.
**Requirement IDs:** D06, D08, D12, D21, D49, D50.

**Acceptance:**
- L07-A: each listed answer has exactly one defined next target after Continue.
- L07-B: Back, edit, help return, unknown and failed-save behavior obey G1; original text and prior confirmed entries survive.
- L07-C: only declared profile writes occur; picture changes obey concept prerequisites.
- L07-D: Choose one explicit answer; no fresh defaults.
- L07-E: open X10 then Return/Escape restores this node’s values, draft, visible question and reading position.

### L08 · Explain costs when receiving care.

**Phase / surface / wireframe:** P3 / lesson / W5. **Prerequisite:** concept:premium.
**Required vocabulary:** contextual inline terms; no forced full lesson. Preflight and G1 apply.

**Exact proposed question:** You may also pay when you get care
**Why asked / microcopy:** A low monthly premium alone does not describe total spending.

| Answer / event | Visible proposed label | Confirmed next target |
|---|---|---|
| `continue` | Continue | `@after_lesson` |
| `know` | I know this | `@after_lesson` |

**Reads:** knowledge.topics.premium. **Allowed writes:** knowledge.topics.care_cost.seen, knowledge.topics.care_cost.selfReport.
**Answer effects:** `*`: Continue marks seen only; I know records explicit topic familiarity; both obey lesson return queue..
**Agent responsibility:** Use the current task and confirmed profile to explain why this matters. Use a clearly labeled example from reviewed content; distinguish deductibles, copays and coinsurance. Never turn example dollars into a personal estimate. Never commit an extracted fact or change the route without confirmation.
**Validation:** Choose one explicit answer; no fresh defaults.
**Picture delta:** `add:care_cost`; add only introduced concept(s), never change enrollment facts. **Progress:** P3 (preserve means unchanged phase). **Help:** L08 plus literal current task and permitted minimum context.
**Requirement IDs:** D06, D08, D12, D21, D49, D50.

**Acceptance:**
- L08-A: each listed answer has exactly one defined next target after Continue.
- L08-B: Back, edit, help return, unknown and failed-save behavior obey G1; original text and prior confirmed entries survive.
- L08-C: only declared profile writes occur; picture changes obey concept prerequisites.
- L08-D: Choose one explicit answer; no fresh defaults.
- L08-E: open X10 then Return/Escape restores this node’s values, draft, visible question and reading position.

### L09 · Teach the cost-limit distinction before choosing a route.

**Phase / surface / wireframe:** P3 / lesson / W5. **Prerequisite:** concept:care_cost.
**Required vocabulary:** contextual inline terms; no forced full lesson. Preflight and G1 apply.

**Exact proposed question:** Check what has a yearly limit—and what does not
**Why asked / microcopy:** Limits apply to defined covered costs. Premiums and other costs can remain.

| Answer / event | Visible proposed label | Confirmed next target |
|---|---|---|
| `continue` | Continue | `@after_lesson` |
| `know` | I know this | `@after_lesson` |

**Reads:** flow.lessonReturn, knowledge.topics.care_cost. **Allowed writes:** knowledge.topics.cost_limit.seen, knowledge.topics.cost_limit.selfReport.
**Answer effects:** `*`: Continue marks seen only; I know records explicit topic familiarity; both obey lesson return queue..
**Agent responsibility:** Use the current task and confirmed profile to explain why this matters. Use source-reviewed statements for Original Medicare and plan medical limits; do not promise a personal annual maximum for everything. Never commit an extracted fact or change the route without confirmation.
**Validation:** Choose one explicit answer; no fresh defaults.
**Picture delta:** `add:cost_limit`; add only introduced concept(s), never change enrollment facts. **Progress:** P3 (preserve means unchanged phase). **Help:** L09 plus literal current task and permitted minimum context.
**Requirement IDs:** D06, D08, D12, D21, D49, D50.

**Acceptance:**
- L09-A: each listed answer has exactly one defined next target after Continue.
- L09-B: Back, edit, help return, unknown and failed-save behavior obey G1; original text and prior confirmed entries survive.
- L09-C: only declared profile writes occur; picture changes obey concept prerequisites.
- L09-D: Choose one explicit answer; no fresh defaults.
- L09-E: open X10 then Return/Escape restores this node’s values, draft, visible question and reading position.

### L10 · Introduce the alternative coverage arrangement.

**Phase / surface / wireframe:** P3 / lesson / W5. **Prerequisite:** concept:original.
**Required vocabulary:** contextual inline terms; no forced full lesson. Preflight and G1 apply.

**Exact proposed question:** Medicare Advantage: A and B through a private plan
**Why asked / microcopy:** The route affects provider rules, costs, and how coverage is arranged.

| Answer / event | Visible proposed label | Confirmed next target |
|---|---|---|
| `continue` | Continue | `@after_lesson` |
| `know` | I know this | `@after_lesson` |

**Reads:** knowledge.topics.original. **Allowed writes:** knowledge.topics.advantage.seen, knowledge.topics.advantage.selfReport.
**Answer effects:** `*`: Continue marks seen only; I know records explicit topic familiarity; both obey lesson return queue..
**Agent responsibility:** Use the current task and confirmed profile to explain why this matters. Use the approved plain-language Advantage explanation; add only the Advantage block, not all optional products. Never commit an extracted fact or change the route without confirmation.
**Validation:** Choose one explicit answer; no fresh defaults.
**Picture delta:** `add:advantage`; add only introduced concept(s), never change enrollment facts. **Progress:** P3 (preserve means unchanged phase). **Help:** L10 plus literal current task and permitted minimum context.
**Requirement IDs:** D06, D08, D12, D21, D49, D50.

**Acceptance:**
- L10-A: each listed answer has exactly one defined next target after Continue.
- L10-B: Back, edit, help return, unknown and failed-save behavior obey G1; original text and prior confirmed entries survive.
- L10-C: only declared profile writes occur; picture changes obey concept prerequisites.
- L10-D: Choose one explicit answer; no fresh defaults.
- L10-E: open X10 then Return/Escape restores this node’s values, draft, visible question and reading position.

### L11 · Connect already-introduced routes and drug coverage.

**Phase / surface / wireframe:** P3 / lesson / W5. **Prerequisite:** concept:advantage.
**Required vocabulary:** contextual inline terms; no forced full lesson. Preflight and G1 apply.

**Exact proposed question:** See how the two routes arrange coverage
**Why asked / microcopy:** This compares structures; it does not select one for you.

| Answer / event | Visible proposed label | Confirmed next target |
|---|---|---|
| `continue` | Continue | `@after_lesson` |
| `know` | I know this | `@after_lesson` |

**Reads:** flow.lessonReturn, knowledge.topics.advantage. **Allowed writes:** knowledge.topics.routes.seen, knowledge.topics.routes.selfReport.
**Answer effects:** `*`: Continue marks seen only; I know records explicit topic familiarity; both obey lesson return queue..
**Agent responsibility:** Use the current task and confirmed profile to explain why this matters. Show Part D within Advantage only if drug concept was introduced; otherwise label “drug coverage: explain” and offer L05 before expanding it. Never commit an extracted fact or change the route without confirmation.
**Validation:** Choose one explicit answer; no fresh defaults.
**Picture delta:** `connect:routes`; add only introduced concept(s), never change enrollment facts. **Progress:** P3 (preserve means unchanged phase). **Help:** L11 plus literal current task and permitted minimum context.
**Requirement IDs:** D06, D08, D12, D21, D49, D50.

**Acceptance:**
- L11-A: each listed answer has exactly one defined next target after Continue.
- L11-B: Back, edit, help return, unknown and failed-save behavior obey G1; original text and prior confirmed entries survive.
- L11-C: only declared profile writes occur; picture changes obey concept prerequisites.
- L11-D: Choose one explicit answer; no fresh defaults.
- L11-E: open X10 then Return/Escape restores this node’s values, draft, visible question and reading position.

### L12 · Introduce supplements only when relevant.

**Phase / surface / wireframe:** P3 / lesson / W5. **Prerequisite:** concept:original+care_cost.
**Required vocabulary:** original, care_cost. Preflight and G1 apply.

**Exact proposed question:** Medigap can help with your share of Original Medicare costs
**Why asked / microcopy:** You asked about supplements or a change where supplement rights may matter.

| Answer / event | Visible proposed label | Confirmed next target |
|---|---|---|
| `continue` | Continue | `@after_lesson` |
| `know` | I know this | `@after_lesson` |

**Reads:** flow.lessonReturn, coverage.current. **Allowed writes:** knowledge.topics.medigap.seen, knowledge.topics.medigap.selfReport.
**Answer effects:** `*`: Continue marks seen only; I know records explicit topic familiarity; both obey lesson return queue..
**Agent responsibility:** Use the current task and confirmed profile to explain why this matters. Place Medigap under Original Medicare. State benefit education is different from a price quote. Never commit an extracted fact or change the route without confirmation.
**Validation:** Choose one explicit answer; no fresh defaults.
**Picture delta:** `add:medigap`; add only introduced concept(s), never change enrollment facts. **Progress:** P3 (preserve means unchanged phase). **Help:** L12 plus literal current task and permitted minimum context.
**Requirement IDs:** D06, D08, D12, D21, D49, D50.

**Acceptance:**
- L12-A: each listed answer has exactly one defined next target after Continue.
- L12-B: Back, edit, help return, unknown and failed-save behavior obey G1; original text and prior confirmed entries survive.
- L12-C: only declared profile writes occur; picture changes obey concept prerequisites.
- L12-D: Choose one explicit answer; no fresh defaults.
- L12-E: open X10 then Return/Escape restores this node’s values, draft, visible question and reading position.

### L13 · Explain that switching rights require separate checking.

**Phase / surface / wireframe:** P3 / lesson / W5. **Prerequisite:** concept:medigap.
**Required vocabulary:** contextual inline terms; no forced full lesson. Preflight and G1 apply.

**Exact proposed question:** Check supplement buying rights before changing coverage
**Why asked / microcopy:** A plan-change period does not by itself establish the right to buy Medigap.

| Answer / event | Visible proposed label | Confirmed next target |
|---|---|---|
| `continue` | Continue | `@after_lesson` |
| `know` | I know this | `@after_lesson` |

**Reads:** coverage.enrollment, coverage.partBStart, coverage.birth, flow.lessonReturn. **Allowed writes:** knowledge.topics.switch_rights.seen, knowledge.topics.switch_rights.selfReport.
**Answer effects:** `*`: Continue marks seen only; I know records explicit topic familiarity; both obey lesson return queue..
**Agent responsibility:** Use the current task and confirmed profile to explain why this matters. Show no exact supplement window without the necessary reviewed date inputs. Unknown eligibility remains open. Never commit an extracted fact or change the route without confirmation.
**Validation:** Choose one explicit answer; no fresh defaults.
**Picture delta:** `annotate:switch_rights`; add only introduced concept(s), never change enrollment facts. **Progress:** P3 (preserve means unchanged phase). **Help:** L13 plus literal current task and permitted minimum context.
**Requirement IDs:** D16, D22, D45, D47, D55.

**Acceptance:**
- L13-A: each listed answer has exactly one defined next target after Continue.
- L13-B: Back, edit, help return, unknown and failed-save behavior obey G1; original text and prior confirmed entries survive.
- L13-C: only declared profile writes occur; picture changes obey concept prerequisites.
- L13-D: Choose one explicit answer; no fresh defaults.
- L13-E: open X10 then Return/Escape restores this node’s values, draft, visible question and reading position.

### C00 · Record enrollment without assuming dates or parts.

**Phase / surface / wireframe:** P2 / single_choice / W1. **Prerequisite:** authenticated_guest_or_ephemeral.
**Required vocabulary:** medicare, part_a, part_b, original. Preflight and G1 apply.

**Exact proposed question:** Do you have Medicare yet?
**Why asked / microcopy:** What is already in place changes which questions are relevant.

| Answer / event | Visible proposed label | Confirmed next target |
|---|---|---|
| `ab` | Yes, Parts A and B | `@after_enrollment` |
| `a` | Yes, Part A only | `@after_enrollment` |
| `parts_unknown` | Yes, but I am not sure which parts | `C01` |
| `no` | No | `C02` |
| `unknown` | I am not sure whether I have Medicare | `C01` |
| `other` | Something else | `X01` |

**Reads:** subject.role, coverage.enrollment. **Allowed writes:** coverage.enrollment.
**Answer effects:** `ab`: coverage.enrollment=ab reported; `a`: coverage.enrollment=a reported; `parts_unknown`: coverage.enrollment=parts_unknown reported; A/B unknown; `no`: coverage.enrollment=no reported; `unknown`: coverage.enrollment=unknown; do not infer no; `other`: proposal only; B-only supported on explicit confirmation.
**Agent responsibility:** Use the current task and confirmed profile to explain why this matters. Offer optional card help only after a relevant enrollment answer. Free text can confirm B only; keep it a distinct supported value. Never commit an extracted fact or change the route without confirmation.
**Validation:** Choose one explicit answer; no fresh defaults.
**Picture delta:** `reference:part_a+part_b`; add only introduced concept(s), never change enrollment facts. **Progress:** P2 (preserve means unchanged phase). **Help:** C00 plus literal current task and permitted minimum context.
**Requirement IDs:** D45, D49, D52.

**Acceptance:**
- C00-A: each listed answer has exactly one defined next target after Continue.
- C00-B: Back, edit, help return, unknown and failed-save behavior obey G1; original text and prior confirmed entries survive.
- C00-C: only declared profile writes occur; picture changes obey concept prerequisites.
- C00-D: Choose one explicit answer; no fresh defaults.
- C00-E: open X10 then Return/Escape restores this node’s values, draft, visible question and reading position.

### C01 · Offer a way to resolve enrollment without blocking learning.

**Phase / surface / wireframe:** P2 / unknown_fact / W1. **Prerequisite:** authenticated_guest_or_ephemeral.
**Required vocabulary:** contextual inline terms; no forced full lesson. Preflight and G1 apply.

**Exact proposed question:** Would you like help checking what is in place?
**Why asked / microcopy:** You can continue while enrollment or parts remain unknown.

| Answer / event | Visible proposed label | Confirmed next target |
|---|---|---|
| `card` | Show optional card guidance | `C01B` |
| `continue` | Keep this unknown and continue | `@after_enrollment` |
| `other` | Something else | `X01` |

**Reads:** coverage.enrollment. **Allowed writes:** checks.enrollment.
**Answer effects:** `*`: Commit only declared fields from the explicit reviewed answer, with typed envelope and original text; unknown/skipped status remains distinct. Non-answer actions mutate only their named control scope..
**Agent responsibility:** Use the current task and confirmed profile to explain why this matters. Keep enrolled-parts-unknown separate from enrollment-unknown. Never commit an extracted fact or change the route without confirmation.
**Validation:** Choose one explicit answer; no fresh defaults.
**Picture delta:** `none`; add only introduced concept(s), never change enrollment facts. **Progress:** P2 (preserve means unchanged phase). **Help:** C01 plus literal current task and permitted minimum context.
**Requirement IDs:** D06, D08, D12, D21, D49, D50.

**Acceptance:**
- C01-A: each listed answer has exactly one defined next target after Continue.
- C01-B: Back, edit, help return, unknown and failed-save behavior obey G1; original text and prior confirmed entries survive.
- C01-C: only declared profile writes occur; picture changes obey concept prerequisites.
- C01-D: Choose one explicit answer; no fresh defaults.
- C01-E: open X10 then Return/Escape restores this node’s values, draft, visible question and reading position.

### C01B · Explain card reading locally.

**Phase / surface / wireframe:** P2 / reference / W1. **Prerequisite:** authenticated_guest_or_ephemeral.
**Required vocabulary:** contextual inline terms; no forced full lesson. Preflight and G1 apply.

**Exact proposed question:** Checking a Medicare card is optional
**Why asked / microcopy:** Look for Hospital (Part A), Medical (Part B), and their separate start dates. Do not enter the card number.

| Answer / event | Visible proposed label | Confirmed next target |
|---|---|---|
| `known` | Update my enrollment answer | `C00` |
| `unknown` | Continue with it unknown | `@after_enrollment` |

**Reads:** coverage.enrollment. **Allowed writes:** checks.enrollment.
**Answer effects:** `*`: Commit only declared fields from the explicit reviewed answer, with typed envelope and original text; unknown/skipped status remains distinct. Non-answer actions mutate only their named control scope..
**Agent responsibility:** Use the current task and confirmed profile to explain why this matters. Do not confuse a private plan card with the Medicare card. Never commit an extracted fact or change the route without confirmation.
**Validation:** No card number, image upload, or document collection.
**Picture delta:** `none`; add only introduced concept(s), never change enrollment facts. **Progress:** P2 (preserve means unchanged phase). **Help:** C01B plus literal current task and permitted minimum context.
**Requirement IDs:** D06, D08, D12, D21, D49, D50.

**Acceptance:**
- C01B-A: each listed answer has exactly one defined next target after Continue.
- C01B-B: Back, edit, help return, unknown and failed-save behavior obey G1; original text and prior confirmed entries survive.
- C01B-C: only declared profile writes occur; picture changes obey concept prerequisites.
- C01B-D: No card number, image upload, or document collection.
- C01B-E: open X10 then Return/Escape restores this node’s values, draft, visible question and reading position.

### C02 · Record a fact relevant to automatic enrollment.

**Phase / surface / wireframe:** P2 / single_choice / W1. **Prerequisite:** authenticated_guest_or_ephemeral.
**Required vocabulary:** contextual inline terms; no forced full lesson. Preflight and G1 apply.

**Exact proposed question:** Do you receive Social Security or Railroad Retirement benefits?
**Why asked / microcopy:** These benefits can affect whether enrollment is automatic; they do not establish the actual start date.

| Answer / event | Visible proposed label | Confirmed next target |
|---|---|---|
| `yes` | Yes | `@after_enrollment` |
| `no` | No | `@after_enrollment` |
| `unknown` | I am not sure | `@after_enrollment` |
| `other` | Something else | `X01` |

**Reads:** subject.role. **Allowed writes:** coverage.socialBenefits.
**Answer effects:** `*`: Commit only declared fields from the explicit reviewed answer, with typed envelope and original text; unknown/skipped status remains distinct. Non-answer actions mutate only their named control scope..
**Agent responsibility:** Use the current task and confirmed profile to explain why this matters. Do not infer enrollment merely from benefits receipt. Never commit an extracted fact or change the route without confirmation.
**Validation:** Choose one explicit answer; no fresh defaults.
**Picture delta:** `none`; add only introduced concept(s), never change enrollment facts. **Progress:** P2 (preserve means unchanged phase). **Help:** C02 plus literal current task and permitted minimum context.
**Requirement IDs:** D06, D08, D12, D21, D49, D50.

**Acceptance:**
- C02-A: each listed answer has exactly one defined next target after Continue.
- C02-B: Back, edit, help return, unknown and failed-save behavior obey G1; original text and prior confirmed entries survive.
- C02-C: only declared profile writes occur; picture changes obey concept prerequisites.
- C02-D: Choose one explicit answer; no fresh defaults.
- C02-E: open X10 then Return/Escape restores this node’s values, draft, visible question and reading position.

### C03 · Identify existing coverage components.

**Phase / surface / wireframe:** P2 / multi_choice / W1. **Prerequisite:** authenticated_guest_or_ephemeral.
**Required vocabulary:** original, routes. Preflight and G1 apply.

**Exact proposed question:** Which coverage do you have now?
**Why asked / microcopy:** This helps us explain what could change without treating existing benefits as missing.

| Answer / event | Visible proposed label | Confirmed next target |
|---|---|---|
| `original` | Original Medicare | `C03` |
| `medigap` | Medicare Supplement / Medigap | `C03` |
| `drug` | Separate prescription drug plan | `C03` |
| `advantage` | Medicare Advantage | `C03` |
| `employer` | Employer or retiree coverage | `C03` |
| `va` | VA, TRICARE or other military coverage | `C03` |
| `medicaid` | Medicaid | `C03` |
| `none` | No other coverage | `C03` |
| `unknown` | I am not sure | `C03` |
| `other` | Something else | `X01` |
| `continue` | Continue | `@after_current` |

**Reads:** coverage.enrollment, intent.goal. **Allowed writes:** coverage.current.
**Answer effects:** `*`: toggle reported coverage component; none/unknown exclusive; Continue commits reviewed set; other proposals need confirmation.
**Agent responsibility:** Use the current task and confirmed profile to explain why this matters. If terms are unfamiliar offer the prerequisite lesson stack before this question; no full-diagram reveal for a novice. Never commit an extracted fact or change the route without confirmation.
**Validation:** Select all relevant components; none/unknown exclusive with components. Incompatible combinations trigger X01 clarification, not rejection or silent correction.
**Picture delta:** `reference:routes`; add only introduced concept(s), never change enrollment facts. **Progress:** P2 (preserve means unchanged phase). **Help:** C03 plus literal current task and permitted minimum context.
**Requirement IDs:** D06, D08, D12, D21, D49, D50.

**Acceptance:**
- C03-A: each listed answer has exactly one defined next target after Continue.
- C03-B: Back, edit, help return, unknown and failed-save behavior obey G1; original text and prior confirmed entries survive.
- C03-C: only declared profile writes occur; picture changes obey concept prerequisites.
- C03-D: Select all relevant components; none/unknown exclusive with components. Incompatible combinations trigger X01 clarification, not rejection or silent correction.
- C03-E: open X10 then Return/Escape restores this node’s values, draft, visible question and reading position.

### C04 · Separate present coverage from desired action.

**Phase / surface / wireframe:** P2 / single_choice / W1. **Prerequisite:** authenticated_guest_or_ephemeral.
**Required vocabulary:** contextual inline terms; no forced full lesson. Preflight and G1 apply.

**Exact proposed question:** What would you like to do with this coverage?
**Why asked / microcopy:** Understanding, keeping, adding, and replacing coverage are different tasks.

| Answer / event | Visible proposed label | Confirmed next target |
|---|---|---|
| `keep` | Understand or keep what I have | `@after_change` |
| `replace` | Compare replacing it | `@after_change` |
| `add` | Explore adding coverage | `@after_change` |
| `unknown` | I am not sure yet | `@after_change` |
| `other` | Something else | `X01` |

**Reads:** coverage.current, intent.goal. **Allowed writes:** intent.change.
**Answer effects:** `*`: Commit only declared fields from the explicit reviewed answer, with typed envelope and original text; unknown/skipped status remains distinct. Non-answer actions mutate only their named control scope..
**Agent responsibility:** Use the current task and confirmed profile to explain why this matters. Keep is a valid outcome. Advantage-to-Original plus Medigap invokes rights teaching before any consequential selection. Never commit an extracted fact or change the route without confirmation.
**Validation:** Choose one explicit answer; no fresh defaults.
**Picture delta:** `none`; add only introduced concept(s), never change enrollment facts. **Progress:** P2 (preserve means unchanged phase). **Help:** C04 plus literal current task and permitted minimum context.
**Requirement IDs:** D06, D08, D12, D21, D49, D50.

**Acceptance:**
- C04-A: each listed answer has exactly one defined next target after Continue.
- C04-B: Back, edit, help return, unknown and failed-save behavior obey G1; original text and prior confirmed entries survive.
- C04-C: only declared profile writes occur; picture changes obey concept prerequisites.
- C04-D: Choose one explicit answer; no fresh defaults.
- C04-E: open X10 then Return/Escape restores this node’s values, draft, visible question and reading position.

### C05 · Record directly known dates only when needed.

**Phase / surface / wireframe:** P2 / optional_dates / W3. **Prerequisite:** authenticated_guest_or_ephemeral.
**Required vocabulary:** contextual inline terms; no forced full lesson. Preflight and G1 apply.

**Exact proposed question:** What birth month and year should we use for age-based timing?
**Why asked / microcopy:** We use this only to explain relevant enrollment windows. Another eligibility reason can change the rules.

| Answer / event | Visible proposed label | Confirmed next target |
|---|---|---|
| `date` | Use the entered month and year | `C06` |
| `unknown` | I do not know, or eligibility is for another reason | `@after_timing` |
| `skip` | Skip dates for now | `@after_timing` |

**Reads:** coverage.enrollment, intent.goal. **Allowed writes:** coverage.birth.
**Answer effects:** `date`: birth.month/year reported from explicit fields; eligibility not established; `unknown`: birth.status=unknown; eligibilityReason=unresolved unless explicitly reported; `skip`: birth.status=skipped.
**Agent responsibility:** Use the current task and confirmed profile to explain why this matters. This is not a universal intake requirement. Do not force a disability/ESRD diagnosis to continue. Never commit an extracted fact or change the route without confirmation.
**Validation:** Valid calendar month/year; not a future birth date; broad historical range; no age-65-year calculation required. Do not persist full birth day.
**Picture delta:** `reference:enrollment_timeline`; add only introduced concept(s), never change enrollment facts. **Progress:** P2 (preserve means unchanged phase). **Help:** C05 plus literal current task and permitted minimum context.
**Requirement IDs:** D06, D08, D12, D21, D49, D50.

**Acceptance:**
- C05-A: each listed answer has exactly one defined next target after Continue.
- C05-B: Back, edit, help return, unknown and failed-save behavior obey G1; original text and prior confirmed entries survive.
- C05-C: only declared profile writes occur; picture changes obey concept prerequisites.
- C05-D: Valid calendar month/year; not a future birth date; broad historical range; no age-65-year calculation required. Do not persist full birth day.
- C05-E: open X10 then Return/Escape restores this node’s values, draft, visible question and reading position.

### C06 · Resolve first-day date edge case without full DOB.

**Phase / surface / wireframe:** P2 / single_choice / W1. **Prerequisite:** authenticated_guest_or_ephemeral.
**Required vocabulary:** contextual inline terms; no forced full lesson. Preflight and G1 apply.

**Exact proposed question:** Is the birthday on the first day of the month?
**Why asked / microcopy:** That detail can shift the age-based enrollment window.

| Answer / event | Visible proposed label | Confirmed next target |
|---|---|---|
| `yes` | Yes | `@after_timing` |
| `no` | No | `@after_timing` |
| `unknown` | I am not sure | `@after_timing` |

**Reads:** coverage.birth. **Allowed writes:** coverage.birth.firstDay.
**Answer effects:** `*`: Commit only declared fields from the explicit reviewed answer, with typed envelope and original text; unknown/skipped status remains distinct. Non-answer actions mutate only their named control scope..
**Agent responsibility:** Use the current task and confirmed profile to explain why this matters. Unknown blocks exact date calculation, not the journey. Never commit an extracted fact or change the route without confirmation.
**Validation:** Choose one explicit answer; no fresh defaults.
**Picture delta:** `none`; add only introduced concept(s), never change enrollment facts. **Progress:** P2 (preserve means unchanged phase). **Help:** C06 plus literal current task and permitted minimum context.
**Requirement IDs:** D06, D08, D12, D21, D49, D50.

**Acceptance:**
- C06-A: each listed answer has exactly one defined next target after Continue.
- C06-B: Back, edit, help return, unknown and failed-save behavior obey G1; original text and prior confirmed entries survive.
- C06-C: only declared profile writes occur; picture changes obey concept prerequisites.
- C06-D: Choose one explicit answer; no fresh defaults.
- C06-E: open X10 then Return/Escape restores this node’s values, draft, visible question and reading position.

### C07 · Record actual Part B effective month separately.

**Phase / surface / wireframe:** P2 / optional_dates / W3. **Prerequisite:** authenticated_guest_or_ephemeral.
**Required vocabulary:** contextual inline terms; no forced full lesson. Preflight and G1 apply.

**Exact proposed question:** Do you know the Part B start month?
**Why asked / microcopy:** A birth month alone does not establish the supplement enrollment window.

| Answer / event | Visible proposed label | Confirmed next target |
|---|---|---|
| `date` | Use the entered Part B month | `@after_part_b` |
| `unknown` | I do not know | `@after_part_b` |
| `not_started` | Part B has not started | `@after_part_b` |
| `skip` | Skip this date for now | `@after_part_b` |

**Reads:** coverage.enrollment, coverage.birth. **Allowed writes:** coverage.partBStart.
**Answer effects:** `date`: Part B start month reported; actual/scheduled flag required; `unknown`: partBStart.status=unknown; `not_started`: partBStart.status=reported; value=not_started; clarify conflicts; `skip`: partBStart.status=skipped.
**Agent responsibility:** Use the current task and confirmed profile to explain why this matters. Ask only for relevant enrollment or supplement-date work; no auto-inferred B date. Never commit an extracted fact or change the route without confirmation.
**Validation:** Valid month/year. Future is labeled scheduled/reported; unknown is not zero. Conflicts with enrollment require X01.
**Picture delta:** `reference:enrollment_timeline`; add only introduced concept(s), never change enrollment facts. **Progress:** P2 (preserve means unchanged phase). **Help:** C07 plus literal current task and permitted minimum context.
**Requirement IDs:** D06, D08, D12, D21, D49, D50.

**Acceptance:**
- C07-A: each listed answer has exactly one defined next target after Continue.
- C07-B: Back, edit, help return, unknown and failed-save behavior obey G1; original text and prior confirmed entries survive.
- C07-C: only declared profile writes occur; picture changes obey concept prerequisites.
- C07-D: Valid month/year. Future is labeled scheduled/reported; unknown is not zero. Conflicts with enrollment require X01.
- C07-E: open X10 then Return/Escape restores this node’s values, draft, visible question and reading position.

### J00 · Distinguish active employment insurance from other coverage.

**Phase / surface / wireframe:** P2 / single_choice / W1. **Prerequisite:** authenticated_guest_or_ephemeral.
**Required vocabulary:** contextual inline terms; no forced full lesson. Preflight and G1 apply.

**Exact proposed question:** Does health insurance come from your own or a spouse’s current job?
**Why asked / microcopy:** COBRA, retiree coverage, and current-job coverage have different rules.

| Answer / event | Visible proposed label | Confirmed next target |
|---|---|---|
| `active` | Yes, insurance from a current job | `J01` |
| `ended` | Employment or its coverage recently ended | `J01` |
| `none` | No current-job coverage | `@after_job` |
| `unknown` | I am not sure which kind it is | `@after_job` |
| `other` | Something else | `X01` |

**Reads:** coverage.enrollment, intent.goal. **Allowed writes:** coverage.job.status.
**Answer effects:** `*`: Commit only declared fields from the explicit reviewed answer, with typed envelope and original text; unknown/skipped status remains distinct. Non-answer actions mutate only their named control scope..
**Agent responsibility:** Use the current task and confirmed profile to explain why this matters. No automatic advice to delay Part B. Other eligibility routes need domain-specific rules. Never commit an extracted fact or change the route without confirmation.
**Validation:** Choose one explicit answer; no fresh defaults.
**Picture delta:** `reference:part_b`; add only introduced concept(s), never change enrollment facts. **Progress:** P2 (preserve means unchanged phase). **Help:** J00 plus literal current task and permitted minimum context.
**Requirement IDs:** D06, D08, D12, D21, D49, D50.

**Acceptance:**
- J00-A: each listed answer has exactly one defined next target after Continue.
- J00-B: Back, edit, help return, unknown and failed-save behavior obey G1; original text and prior confirmed entries survive.
- J00-C: only declared profile writes occur; picture changes obey concept prerequisites.
- J00-D: Choose one explicit answer; no fresh defaults.
- J00-E: open X10 then Return/Escape restores this node’s values, draft, visible question and reading position.

### J01 · Set the transition task without forcing shopping.

**Phase / surface / wireframe:** P2 / single_choice / W1. **Prerequisite:** authenticated_guest_or_ephemeral.
**Required vocabulary:** contextual inline terms; no forced full lesson. Preflight and G1 apply.

**Exact proposed question:** What would help with the job coverage?
**Why asked / microcopy:** We can prepare next-step questions or explore coverage for the transition.

| Answer / event | Visible proposed label | Confirmed next target |
|---|---|---|
| `prepare` | Prepare a transition plan | `J02` |
| `compare` | Explore Medicare coverage for the transition | `J02` |
| `unknown` | Help me work out the next step | `J02` |
| `other` | Something else | `X01` |

**Reads:** intent.goal, coverage.job.status. **Allowed writes:** intent.jobTask.
**Answer effects:** `*`: Commit only declared fields from the explicit reviewed answer, with typed envelope and original text; unknown/skipped status remains distinct. Non-answer actions mutate only their named control scope..
**Agent responsibility:** Use the current task and confirmed profile to explain why this matters.  Never commit an extracted fact or change the route without confirmation.
**Validation:** Choose one explicit answer; no fresh defaults.
**Picture delta:** `none`; add only introduced concept(s), never change enrollment facts. **Progress:** P2 (preserve means unchanged phase). **Help:** J01 plus literal current task and permitted minimum context.
**Requirement IDs:** D06, D08, D12, D21, D49, D50.

**Acceptance:**
- J01-A: each listed answer has exactly one defined next target after Continue.
- J01-B: Back, edit, help return, unknown and failed-save behavior obey G1; original text and prior confirmed entries survive.
- J01-C: only declared profile writes occur; picture changes obey concept prerequisites.
- J01-D: Choose one explicit answer; no fresh defaults.
- J01-E: open X10 then Return/Escape restores this node’s values, draft, visible question and reading position.

### J02 · Record employer-size information without deciding coordination.

**Phase / surface / wireframe:** P2 / single_choice / W1. **Prerequisite:** authenticated_guest_or_ephemeral.
**Required vocabulary:** contextual inline terms; no forced full lesson. Preflight and G1 apply.

**Exact proposed question:** How many employees does the employer have?
**Why asked / microcopy:** Employer size can matter, but the benefits office must confirm how the coverage coordinates.

| Answer / event | Visible proposed label | Confirmed next target |
|---|---|---|
| `large` | 20 or more | `J03` |
| `small` | Fewer than 20 | `J03` |
| `unknown` | I do not know | `J03` |
| `other` | Something else | `X01` |

**Reads:** coverage.job.status. **Allowed writes:** coverage.job.employerSize.
**Answer effects:** `*`: Commit only declared fields from the explicit reviewed answer, with typed envelope and original text; unknown/skipped status remains distinct. Non-answer actions mutate only their named control scope..
**Agent responsibility:** Use the current task and confirmed profile to explain why this matters. Under-65/disability contexts must not reuse an age-65 threshold; mark separate rule review and offer official help. Never commit an extracted fact or change the route without confirmation.
**Validation:** Choose one explicit answer; no fresh defaults.
**Picture delta:** `none`; add only introduced concept(s), never change enrollment facts. **Progress:** P2 (preserve means unchanged phase). **Help:** J02 plus literal current task and permitted minimum context.
**Requirement IDs:** D06, D08, D12, D21, D49, D50.

**Acceptance:**
- J02-A: each listed answer has exactly one defined next target after Continue.
- J02-B: Back, edit, help return, unknown and failed-save behavior obey G1; original text and prior confirmed entries survive.
- J02-C: only declared profile writes occur; picture changes obey concept prerequisites.
- J02-D: Choose one explicit answer; no fresh defaults.
- J02-E: open X10 then Return/Escape restores this node’s values, draft, visible question and reading position.

### J03 · Keep employment end distinct from insurance end.

**Phase / surface / wireframe:** P2 / optional_dates / W3. **Prerequisite:** authenticated_guest_or_ephemeral; job goal or current/recent employment context; employer size may remain unknown.
**Required vocabulary:** contextual inline terms; no forced full lesson. Preflight and G1 apply.

**Exact proposed question:** When does employment end?
**Why asked / microcopy:** Employment and insurance may end at different times.

| Answer / event | Visible proposed label | Confirmed next target |
|---|---|---|
| `date` | Use the entered employment end month | `J04` |
| `unknown` | I do not know yet | `J04` |
| `ongoing` | Employment is continuing | `J04` |

**Reads:** coverage.job.status. **Allowed writes:** coverage.job.employmentEnd.
**Answer effects:** `*`: Commit only declared fields from the explicit reviewed answer, with typed envelope and original text; unknown/skipped status remains distinct. Non-answer actions mutate only their named control scope..
**Agent responsibility:** Use the current task and confirmed profile to explain why this matters.  Never commit an extracted fact or change the route without confirmation.
**Validation:** Valid month/year or explicit unknown/ongoing. Record actual versus expected separately; no definitive deadline from a forecast.
**Picture delta:** `reference:enrollment_timeline`; add only introduced concept(s), never change enrollment facts. **Progress:** P2 (preserve means unchanged phase). **Help:** J03 plus literal current task and permitted minimum context.
**Requirement IDs:** D06, D08, D12, D21, D49, D50.

**Acceptance:**
- J03-A: each listed answer has exactly one defined next target after Continue.
- J03-B: Back, edit, help return, unknown and failed-save behavior obey G1; original text and prior confirmed entries survive.
- J03-C: only declared profile writes occur; picture changes obey concept prerequisites.
- J03-D: Valid month/year or explicit unknown/ongoing. Record actual versus expected separately; no definitive deadline from a forecast.
- J03-E: open X10 then Return/Escape restores this node’s values, draft, visible question and reading position.

### J04 · Record the distinct health coverage end.

**Phase / surface / wireframe:** P2 / optional_dates / W3. **Prerequisite:** authenticated_guest_or_ephemeral.
**Required vocabulary:** contextual inline terms; no forced full lesson. Preflight and G1 apply.

**Exact proposed question:** When does the job health coverage end?
**Why asked / microcopy:** We keep this separate so the next-step questions reflect the actual situation.

| Answer / event | Visible proposed label | Confirmed next target |
|---|---|---|
| `date` | Use the entered coverage end month | `J05` |
| `unknown` | I do not know yet | `J05` |
| `ongoing` | Coverage is continuing | `J05` |

**Reads:** coverage.job.employmentEnd. **Allowed writes:** coverage.job.coverageEnd.
**Answer effects:** `*`: Commit only declared fields from the explicit reviewed answer, with typed envelope and original text; unknown/skipped status remains distinct. Non-answer actions mutate only their named control scope..
**Agent responsibility:** Use the current task and confirmed profile to explain why this matters.  Never commit an extracted fact or change the route without confirmation.
**Validation:** Same as J03; dates may differ. Do not reject a real difference; ask if inconsistent.
**Picture delta:** `reference:enrollment_timeline`; add only introduced concept(s), never change enrollment facts. **Progress:** P2 (preserve means unchanged phase). **Help:** J04 plus literal current task and permitted minimum context.
**Requirement IDs:** D06, D08, D12, D21, D49, D50.

**Acceptance:**
- J04-A: each listed answer has exactly one defined next target after Continue.
- J04-B: Back, edit, help return, unknown and failed-save behavior obey G1; original text and prior confirmed entries survive.
- J04-C: only declared profile writes occur; picture changes obey concept prerequisites.
- J04-D: Same as J03; dates may differ. Do not reject a real difference; ask if inconsistent.
- J04-E: open X10 then Return/Escape restores this node’s values, draft, visible question and reading position.

### J05 · Preserve creditable-drug uncertainty.

**Phase / surface / wireframe:** P2 / single_choice / W1. **Prerequisite:** authenticated_guest_or_ephemeral.
**Required vocabulary:** contextual inline terms; no forced full lesson. Preflight and G1 apply.

**Exact proposed question:** Has the current coverage confirmed that its drug coverage is creditable?
**Why asked / microcopy:** A written notice helps establish the drug-coverage questions before a change.

| Answer / event | Visible proposed label | Confirmed next target |
|---|---|---|
| `yes` | Yes, I have a notice | `@after_transition` |
| `no` | No, it says it is not creditable | `@after_transition` |
| `unknown` | I do not know / need the notice | `@after_transition` |
| `none` | There is no drug coverage | `@after_transition` |
| `other` | Something else | `X01` |

**Reads:** coverage.current, coverage.job. **Allowed writes:** coverage.creditableDrug.
**Answer effects:** `*`: Commit only declared fields from the explicit reviewed answer, with typed envelope and original text; unknown/skipped status remains distinct. Non-answer actions mutate only their named control scope..
**Agent responsibility:** Use the current task and confirmed profile to explain why this matters. Reported notice receipt is not an independently verified notice. Do not request an upload. Never commit an extracted fact or change the route without confirmation.
**Validation:** Choose one explicit answer; no fresh defaults.
**Picture delta:** `none`; add only introduced concept(s), never change enrollment facts. **Progress:** P2 (preserve means unchanged phase). **Help:** J05 plus literal current task and permitted minimum context.
**Requirement IDs:** D06, D08, D12, D21, D49, D50.

**Acceptance:**
- J05-A: each listed answer has exactly one defined next target after Continue.
- J05-B: Back, edit, help return, unknown and failed-save behavior obey G1; original text and prior confirmed entries survive.
- J05-C: only declared profile writes occur; picture changes obey concept prerequisites.
- J05-D: Choose one explicit answer; no fresh defaults.
- J05-E: open X10 then Return/Escape restores this node’s values, draft, visible question and reading position.

### N00 · Record medicine-check needs without inferring coverage.

**Phase / surface / wireframe:** P2 / single_choice / W1. **Prerequisite:** authenticated_guest_or_ephemeral.
**Required vocabulary:** drugs. Preflight and G1 apply.

**Exact proposed question:** Do you take prescription medicines?
**Why asked / microcopy:** This helps us prepare the medicine and pharmacy checks that matter to you.

| Answer / event | Visible proposed label | Confirmed next target |
|---|---|---|
| `yes` | Yes | `N01` |
| `no` | No | `@after_medicines` |
| `unknown` | I am not sure / need a list | `N01` |
| `other` | Something else | `X01` |

**Reads:** coverage.current. **Allowed writes:** needs.medicinesStatus.
**Answer effects:** `*`: Commit only declared fields from the explicit reviewed answer, with typed envelope and original text; unknown/skipped status remains distinct. Non-answer actions mutate only their named control scope..
**Agent responsibility:** Use the current task and confirmed profile to explain why this matters. No medicines does not mean drug coverage is unnecessary. Never commit an extracted fact or change the route without confirmation.
**Validation:** Choose one explicit answer; no fresh defaults.
**Picture delta:** `reference:drugs`; add only introduced concept(s), never change enrollment facts. **Progress:** P2 (preserve means unchanged phase). **Help:** N00 plus literal current task and permitted minimum context.
**Requirement IDs:** D06, D08, D12, D21, D49, D50.

**Acceptance:**
- N00-A: each listed answer has exactly one defined next target after Continue.
- N00-B: Back, edit, help return, unknown and failed-save behavior obey G1; original text and prior confirmed entries survive.
- N00-C: only declared profile writes occur; picture changes obey concept prerequisites.
- N00-D: Choose one explicit answer; no fresh defaults.
- N00-E: open X10 then Return/Escape restores this node’s values, draft, visible question and reading position.

### N01 · Build an optional medicine list.

**Phase / surface / wireframe:** P2 / sensitive_list / W3. **Prerequisite:** authenticated_guest_or_ephemeral.
**Required vocabulary:** contextual inline terms; no forced full lesson. Preflight and G1 apply.

**Exact proposed question:** Would you like to add medicines to the checking list?
**Why asked / microcopy:** Exact names, strength and form can help later. Coverage and costs remain unchecked here.

| Answer / event | Visible proposed label | Confirmed next target |
|---|---|---|
| `save` | Save the reviewed list | `N02` |
| `skip` | Continue without medicine details | `N02` |

**Reads:** privacy.sensitiveChoice, needs.medicinesStatus. **Allowed writes:** needs.medications.
**Answer effects:** `*`: Commit only declared fields from the explicit reviewed answer, with typed envelope and original text; unknown/skipped status remains distinct. Non-answer actions mutate only their named control scope..
**Agent responsibility:** Use the current task and confirmed profile to explain why this matters. Extract candidate items for X01 confirmation; retain original text. A drug-name match never means formulary or pharmacy price verified. Never commit an extracted fact or change the route without confirmation.
**Validation:** Per item name + optional strength/form/directions; unresolved names retained. List 0–50 before a review-size warning; no guesses. Separate sensitive-save choice precedes durable storage.
**Picture delta:** `none`; add only introduced concept(s), never change enrollment facts. **Progress:** P2 (preserve means unchanged phase). **Help:** N01 plus literal current task and permitted minimum context.
**Requirement IDs:** D06, D08, D12, D21, D49, D50.

**Acceptance:**
- N01-A: each listed answer has exactly one defined next target after Continue.
- N01-B: Back, edit, help return, unknown and failed-save behavior obey G1; original text and prior confirmed entries survive.
- N01-C: only declared profile writes occur; picture changes obey concept prerequisites.
- N01-D: Per item name + optional strength/form/directions; unresolved names retained. List 0–50 before a review-size warning; no guesses. Separate sensitive-save choice precedes durable storage.
- N01-E: open X10 then Return/Escape restores this node’s values, draft, visible question and reading position.

### N02 · Record pharmacy preference only when useful.

**Phase / surface / wireframe:** P2 / sensitive_list / W3. **Prerequisite:** authenticated_guest_or_ephemeral.
**Required vocabulary:** contextual inline terms; no forced full lesson. Preflight and G1 apply.

**Exact proposed question:** Is there a pharmacy you would like to check?
**Why asked / microcopy:** A pharmacy name alone does not establish network status or prices.

| Answer / event | Visible proposed label | Confirmed next target |
|---|---|---|
| `save` | Use the reviewed pharmacy | `@after_medicines` |
| `skip` | Skip pharmacy for now | `@after_medicines` |
| `unknown` | I am not sure | `@after_medicines` |

**Reads:** needs.medications, privacy.sensitiveChoice. **Allowed writes:** needs.pharmacies.
**Answer effects:** `*`: Commit only declared fields from the explicit reviewed answer, with typed envelope and original text; unknown/skipped status remains distinct. Non-answer actions mutate only their named control scope..
**Agent responsibility:** Use the current task and confirmed profile to explain why this matters.  Never commit an extracted fact or change the route without confirmation.
**Validation:** Optional name/location; ambiguous matches need explicit confirmation. No exact costs without supported pricing service.
**Picture delta:** `none`; add only introduced concept(s), never change enrollment facts. **Progress:** P2 (preserve means unchanged phase). **Help:** N02 plus literal current task and permitted minimum context.
**Requirement IDs:** D06, D08, D12, D21, D49, D50.

**Acceptance:**
- N02-A: each listed answer has exactly one defined next target after Continue.
- N02-B: Back, edit, help return, unknown and failed-save behavior obey G1; original text and prior confirmed entries survive.
- N02-C: only declared profile writes occur; picture changes obey concept prerequisites.
- N02-D: Optional name/location; ambiguous matches need explicit confirmation. No exact costs without supported pricing service.
- N02-E: open X10 then Return/Escape restores this node’s values, draft, visible question and reading position.

### N03 · Keep benefit needs distinct from verified benefits.

**Phase / surface / wireframe:** P2 / multi_choice / W1. **Prerequisite:** authenticated_guest_or_ephemeral.
**Required vocabulary:** extras. Preflight and G1 apply.

**Exact proposed question:** Which dental, vision or hearing needs should we check?
**Why asked / microcopy:** Plan labels do not establish covered treatment, providers or allowances.

| Answer / event | Visible proposed label | Confirmed next target |
|---|---|---|
| `dental` | Dental | `N03` |
| `vision` | Vision | `N03` |
| `hearing` | Hearing | `N03` |
| `none` | None of these | `N03` |
| `unknown` | I am not sure yet | `N03` |
| `other` | Something else | `X01` |
| `continue` | Continue | `N04` |

**Reads:** coverage.current. **Allowed writes:** needs.extras.
**Answer effects:** `*`: Commit only declared fields from the explicit reviewed answer, with typed envelope and original text; unknown/skipped status remains distinct. Non-answer actions mutate only their named control scope..
**Agent responsibility:** Use the current task and confirmed profile to explain why this matters.  Never commit an extracted fact or change the route without confirmation.
**Validation:** Multiple needs allowed; none/unknown exclusive; cannot silently treat an unanswered group as none.
**Picture delta:** `reference:extras`; add only introduced concept(s), never change enrollment facts. **Progress:** P2 (preserve means unchanged phase). **Help:** N03 plus literal current task and permitted minimum context.
**Requirement IDs:** D06, D08, D12, D21, D49, D50.

**Acceptance:**
- N03-A: each listed answer has exactly one defined next target after Continue.
- N03-B: Back, edit, help return, unknown and failed-save behavior obey G1; original text and prior confirmed entries survive.
- N03-C: only declared profile writes occur; picture changes obey concept prerequisites.
- N03-D: Multiple needs allowed; none/unknown exclusive; cannot silently treat an unanswered group as none.
- N03-E: open X10 then Return/Escape restores this node’s values, draft, visible question and reading position.

### N04 · Record priorities without substituting them for facts.

**Phase / surface / wireframe:** P2 / multi_choice / W1. **Prerequisite:** authenticated_guest_or_ephemeral.
**Required vocabulary:** premium, care_cost, cost_limit. Preflight and G1 apply.

**Exact proposed question:** What is most important to you?
**Why asked / microcopy:** Your priorities help explain tradeoffs. Only supported published fields can affect ordering.

| Answer / event | Visible proposed label | Confirmed next target |
|---|---|---|
| `doctors` | Keeping my doctors | `N04` |
| `travel` | Care away from home | `N04` |
| `premium` | Lower monthly payments | `N04` |
| `bills` | More predictable care bills | `N04` |
| `drugs` | Checking my medicines | `N04` |
| `unknown` | I am not sure yet | `N04` |
| `other` | Something else | `X01` |
| `continue` | Continue | `@after_priorities` |

**Reads:** needs, coverage.current. **Allowed writes:** needs.priorities.
**Answer effects:** `*`: Commit only declared fields from the explicit reviewed answer, with typed envelope and original text; unknown/skipped status remains distinct. Non-answer actions mutate only their named control scope..
**Agent responsibility:** Use the current task and confirmed profile to explain why this matters. Only ask N05 for multiple actual priorities; do not require a top priority to continue. Never commit an extracted fact or change the route without confirmation.
**Validation:** Select any or explicitly continue without a priority. Unknown exclusive with specifics. Priorities never confirm eligibility or personal fit.
**Picture delta:** `none`; add only introduced concept(s), never change enrollment facts. **Progress:** P2 (preserve means unchanged phase). **Help:** N04 plus literal current task and permitted minimum context.
**Requirement IDs:** D06, D08, D12, D21, D49, D50.

**Acceptance:**
- N04-A: each listed answer has exactly one defined next target after Continue.
- N04-B: Back, edit, help return, unknown and failed-save behavior obey G1; original text and prior confirmed entries survive.
- N04-C: only declared profile writes occur; picture changes obey concept prerequisites.
- N04-D: Select any or explicitly continue without a priority. Unknown exclusive with specifics. Priorities never confirm eligibility or personal fit.
- N04-E: open X10 then Return/Escape restores this node’s values, draft, visible question and reading position.

### N05 · Make conflicting priorities visible.

**Phase / surface / wireframe:** P2 / optional_choice / W1. **Prerequisite:** authenticated_guest_or_ephemeral.
**Required vocabulary:** contextual inline terms; no forced full lesson. Preflight and G1 apply.

**Exact proposed question:** If these pull in different directions, which matters most?
**Why asked / microcopy:** This can change an explicitly labeled supported sort; it cannot resolve personal suitability.

| Answer / event | Visible proposed label | Confirmed next target |
|---|---|---|
| `dynamic` | One of my selected priorities | `@after_priority_order` |
| `equal` | Keep them equally important | `@after_priority_order` |
| `unknown` | I am not sure | `@after_priority_order` |

**Reads:** needs.priorities. **Allowed writes:** needs.priorityOrder.
**Answer effects:** `*`: Commit only declared fields from the explicit reviewed answer, with typed envelope and original text; unknown/skipped status remains distinct. Non-answer actions mutate only their named control scope..
**Agent responsibility:** Use the current task and confirmed profile to explain why this matters.  Never commit an extracted fact or change the route without confirmation.
**Validation:** Dynamic option expands to one option per prior confirmed priority, IDs priority:<key>. Never introduce unselected priorities.
**Picture delta:** `none`; add only introduced concept(s), never change enrollment facts. **Progress:** P2 (preserve means unchanged phase). **Help:** N05 plus literal current task and permitted minimum context.
**Requirement IDs:** D06, D08, D12, D21, D49, D50.

**Acceptance:**
- N05-A: each listed answer has exactly one defined next target after Continue.
- N05-B: Back, edit, help return, unknown and failed-save behavior obey G1; original text and prior confirmed entries survive.
- N05-C: only declared profile writes occur; picture changes obey concept prerequisites.
- N05-D: Dynamic option expands to one option per prior confirmed priority, IDs priority:<key>. Never introduce unselected priorities.
- N05-E: open X10 then Return/Escape restores this node’s values, draft, visible question and reading position.

### N06 · Turn provider preferences into checking tasks.

**Phase / surface / wireframe:** P2 / sensitive_list / W3. **Prerequisite:** authenticated_guest_or_ephemeral.
**Required vocabulary:** contextual inline terms; no forced full lesson. Preflight and G1 apply.

**Exact proposed question:** Which doctors or hospitals would you like to check?
**Why asked / microcopy:** We need the exact provider and plan before anyone can confirm participation.

| Answer / event | Visible proposed label | Confirmed next target |
|---|---|---|
| `save` | Save the reviewed checking list | `@after_providers` |
| `skip` | Continue without names | `@after_providers` |

**Reads:** needs.priorities, privacy.sensitiveChoice. **Allowed writes:** needs.providers.
**Answer effects:** `*`: Commit only declared fields from the explicit reviewed answer, with typed envelope and original text; unknown/skipped status remains distinct. Non-answer actions mutate only their named control scope..
**Agent responsibility:** Use the current task and confirmed profile to explain why this matters. Sensitive-save control precedes durable storage. Names must not cause automatic plan exclusion. Never commit an extracted fact or change the route without confirmation.
**Validation:** Optional name + specialty/location; ambiguous entities unconfirmed. No Medicare number or clinical history required.
**Picture delta:** `none`; add only introduced concept(s), never change enrollment facts. **Progress:** P2 (preserve means unchanged phase). **Help:** N06 plus literal current task and permitted minimum context.
**Requirement IDs:** D06, D08, D12, D21, D49, D50.

**Acceptance:**
- N06-A: each listed answer has exactly one defined next target after Continue.
- N06-B: Back, edit, help return, unknown and failed-save behavior obey G1; original text and prior confirmed entries survive.
- N06-C: only declared profile writes occur; picture changes obey concept prerequisites.
- N06-D: Optional name + specialty/location; ambiguous entities unconfirmed. No Medicare number or clinical history required.
- N06-E: open X10 then Return/Escape restores this node’s values, draft, visible question and reading position.

### O00 · Clarify the comparison target without assuming expertise.

**Phase / surface / wireframe:** P3 / single_choice / W1. **Prerequisite:** authenticated_guest_or_ephemeral.
**Required vocabulary:** contextual inline terms; no forced full lesson. Preflight and G1 apply.

**Exact proposed question:** Which plans or options would you like to compare?
**Why asked / microcopy:** Coverage categories serve different purposes.

| Answer / event | Visible proposed label | Confirmed next target |
|---|---|---|
| `advantage` | Medicare Advantage plans | `O01` |
| `medigap` | Medicare Supplement / Medigap | `L12` |
| `drugs` | Separate prescription drug plans | `O01` |
| `named` | Plans I already have in mind | `O02` |
| `difference` | Help me understand the difference | `L10` |
| `other` | Something else | `X01` |

**Reads:** intent.goal, intent.change, knowledge. **Allowed writes:** intent.compareKind.
**Answer effects:** `*`: Commit only declared fields from the explicit reviewed answer, with typed envelope and original text; unknown/skipped status remains distinct. Non-answer actions mutate only their named control scope..
**Agent responsibility:** Use the current task and confirmed profile to explain why this matters. Novice prerequisites are inserted before unfamiliar categories are used as consequential choices. Choosing a category is not an enrollment preference. Never commit an extracted fact or change the route without confirmation. Category names here are topic discovery, with inline definitions; selecting one schedules its missing category_prerequisites before a consequential comparison. Do not expand unintroduced blocks.
**Validation:** Choose one explicit answer; no fresh defaults.
**Picture delta:** `reference:eligible_concepts`; add only introduced concept(s), never change enrollment facts. **Progress:** P3 (preserve means unchanged phase). **Help:** O00 plus literal current task and permitted minimum context.
**Requirement IDs:** D31, D41, D47, D49, D55.

**Acceptance:**
- O00-A: each listed answer has exactly one defined next target after Continue.
- O00-B: Back, edit, help return, unknown and failed-save behavior obey G1; original text and prior confirmed entries survive.
- O00-C: only declared profile writes occur; picture changes obey concept prerequisites.
- O00-D: Choose one explicit answer; no fresh defaults.
- O00-E: open X10 then Return/Escape restores this node’s values, draft, visible question and reading position.

### O01 · Distinguish published browsing from personal change review.

**Phase / surface / wireframe:** P3 / scope / W1. **Prerequisite:** authenticated_guest_or_ephemeral.
**Required vocabulary:** contextual inline terms; no forced full lesson. Preflight and G1 apply.

**Exact proposed question:** How would you like to explore these options?
**Why asked / microcopy:** Browsing needs location and year. Reviewing a personal change needs relevant coverage facts too.

| Answer / event | Visible proposed label | Confirmed next target |
|---|---|---|
| `browse` | Browse published plan facts | `O03` |
| `personal` | Review a possible change for me | `@personal_entry` |
| `unknown` | I am not sure—show me what is available | `O03` |

**Reads:** intent.compareKind, coverage.enrollment. **Allowed writes:** intent.comparisonMode.
**Answer effects:** `browse`: comparisonMode=browse; personalReview=false; `personal`: comparisonMode=personal; personalReview=true; `unknown`: comparisonMode=browse; intent remains uncertain.
**Agent responsibility:** Use the current task and confirmed profile to explain why this matters. No doctor/medicine/full enrollment intake before ordinary browsing. Label missing personal checks explicitly. Never commit an extracted fact or change the route without confirmation.
**Validation:** Choose one explicit answer; no fresh defaults.
**Picture delta:** `none`; add only introduced concept(s), never change enrollment facts. **Progress:** P3 (preserve means unchanged phase). **Help:** O01 plus literal current task and permitted minimum context.
**Requirement IDs:** D06, D08, D12, D21, D49, D50.

**Acceptance:**
- O01-A: each listed answer has exactly one defined next target after Continue.
- O01-B: Back, edit, help return, unknown and failed-save behavior obey G1; original text and prior confirmed entries survive.
- O01-C: only declared profile writes occur; picture changes obey concept prerequisites.
- O01-D: Choose one explicit answer; no fresh defaults.
- O01-E: open X10 then Return/Escape restores this node’s values, draft, visible question and reading position.

### O02 · Capture named candidates without choosing ambiguous matches.

**Phase / surface / wireframe:** P3 / free_text / W3. **Prerequisite:** authenticated_guest_or_ephemeral.
**Required vocabulary:** contextual inline terms; no forced full lesson. Preflight and G1 apply.

**Exact proposed question:** Which plans do you have in mind?
**Why asked / microcopy:** Exact plan name, company, year and location help prevent comparing the wrong records.

| Answer / event | Visible proposed label | Confirmed next target |
|---|---|---|
| `search` | Find matching published records | `O03` |
| `unknown` | I do not know the exact names | `O00` |

**Reads:** intent.compareKind. **Allowed writes:** comparison.requestedNames.
**Answer effects:** `*`: Commit only declared fields from the explicit reviewed answer, with typed envelope and original text; unknown/skipped status remains distinct. Non-answer actions mutate only their named control scope..
**Agent responsibility:** Use the current task and confirmed profile to explain why this matters.  Never commit an extracted fact or change the route without confirmation.
**Validation:** 0–1200 characters; plan names are search text, not selected IDs. Resolve matches after location/year in O06.
**Picture delta:** `none`; add only introduced concept(s), never change enrollment facts. **Progress:** P3 (preserve means unchanged phase). **Help:** O02 plus literal current task and permitted minimum context.
**Requirement IDs:** D06, D08, D12, D21, D49, D50.

**Acceptance:**
- O02-A: each listed answer has exactly one defined next target after Continue.
- O02-B: Back, edit, help return, unknown and failed-save behavior obey G1; original text and prior confirmed entries survive.
- O02-C: only declared profile writes occur; picture changes obey concept prerequisites.
- O02-D: 0–1200 characters; plan names are search text, not selected IDs. Resolve matches after location/year in O06.
- O02-E: open X10 then Return/Escape restores this node’s values, draft, visible question and reading position.

### O03 · Establish catalog geography only when relevant.

**Phase / surface / wireframe:** P3 / location / W1. **Prerequisite:** authenticated_guest_or_ephemeral.
**Required vocabulary:** contextual inline terms; no forced full lesson. Preflight and G1 apply.

**Exact proposed question:** What is the home ZIP code?
**Why asked / microcopy:** Published plans can depend on where the person receiving coverage lives.

| Answer / event | Visible proposed label | Confirmed next target |
|---|---|---|
| `valid` | Use this ZIP code | `O04` |
| `unknown` | I do not know it | `O05` |
| `skip` | Continue without local records | `O05` |

**Reads:** subject.role, comparison.scope. **Allowed writes:** comparison.scope.zip.
**Answer effects:** `*`: Commit only declared fields from the explicit reviewed answer, with typed envelope and original text; unknown/skipped status remains distinct. Non-answer actions mutate only their named control scope..
**Agent responsibility:** Use the current task and confirmed profile to explain why this matters. Do not ask this on pure education routes. Never commit an extracted fact or change the route without confirmation.
**Validation:** Five digits; preserve leading zero; Enter submits only this valid form. Invalid stays at O03 with linked error. No external geocoder by default.
**Picture delta:** `reference:eligible_concepts`; add only introduced concept(s), never change enrollment facts. **Progress:** P3 (preserve means unchanged phase). **Help:** O03 plus literal current task and permitted minimum context.
**Requirement IDs:** D14, D46, D49.

**Acceptance:**
- O03-A: each listed answer has exactly one defined next target after Continue.
- O03-B: Back, edit, help return, unknown and failed-save behavior obey G1; original text and prior confirmed entries survive.
- O03-C: only declared profile writes occur; picture changes obey concept prerequisites.
- O03-D: Five digits; preserve leading zero; Enter submits only this valid form. Invalid stays at O03 with linked error. No external geocoder by default.
- O03-E: open X10 then Return/Escape restores this node’s values, draft, visible question and reading position.

### O04 · Resolve geography without a redundant confirmation.

**Phase / surface / wireframe:** P3 / lookup / W1. **Prerequisite:** authenticated_guest_or_ephemeral.
**Required vocabulary:** contextual inline terms; no forced full lesson. Preflight and G1 apply.

**Exact proposed question:** Checking the location
**Why asked / microcopy:** We ask a county only when the maintained reference cannot resolve one match.

| Answer / event | Visible proposed label | Confirmed next target |
|---|---|---|
| `unique` | One reliable match | `O05` |
| `multiple` | Several county matches | `O04B` |
| `missing` | No reliable match | `O04B` |
| `error` | Lookup unavailable | `O04B` |

**Reads:** comparison.scope.zip. **Allowed writes:** comparison.scope.county, comparison.scope.locationEvidence.
**Answer effects:** `*`: system result sets sourced location or unresolved match list; never user-reported confirmation or invented county.
**Agent responsibility:** Use the current task and confirmed profile to explain why this matters.  Never commit an extracted fact or change the route without confirmation.
**Validation:** This is a system result, not selectable answer buttons. Preserve source/version/date and every county association. Never choose by address share.
**Picture delta:** `none`; add only introduced concept(s), never change enrollment facts. **Progress:** P3 (preserve means unchanged phase). **Help:** O04 plus literal current task and permitted minimum context.
**Requirement IDs:** D06, D08, D12, D21, D49, D50.

**Acceptance:**
- O04-A: each listed answer has exactly one defined next target after Continue.
- O04-B: Back, edit, help return, unknown and failed-save behavior obey G1; original text and prior confirmed entries survive.
- O04-C: only declared profile writes occur; picture changes obey concept prerequisites.
- O04-D: This is a system result, not selectable answer buttons. Preserve source/version/date and every county association. Never choose by address share.
- O04-E: open X10 then Return/Escape restores this node’s values, draft, visible question and reading position.

### O04B · Resolve actual geographic ambiguity.

**Phase / surface / wireframe:** P3 / single_choice / W1. **Prerequisite:** authenticated_guest_or_ephemeral.
**Required vocabulary:** contextual inline terms; no forced full lesson. Preflight and G1 apply.

**Exact proposed question:** Which county is the home in?
**Why asked / microcopy:** ZIP codes can cross county lines. It is fine to keep the county unknown.

| Answer / event | Visible proposed label | Confirmed next target |
|---|---|---|
| `dynamic` | One of the sourced county matches | `O05` |
| `different` | A different county | `O05` |
| `unknown` | I am not sure | `O05` |
| `edit` | Change ZIP code | `O03` |

**Reads:** comparison.scope.zip, comparison.scope.locationEvidence. **Allowed writes:** comparison.scope.county.
**Answer effects:** `*`: Commit only declared fields from the explicit reviewed answer, with typed envelope and original text; unknown/skipped status remains distinct. Non-answer actions mutate only their named control scope..
**Agent responsibility:** Use the current task and confirmed profile to explain why this matters.  Never commit an extracted fact or change the route without confirmation.
**Validation:** Dynamic expands all source matches with IDs county:<FIPS>; no default. Missing lookup permits reported county/state with provenance, never fabricates crosswalk evidence.
**Picture delta:** `none`; add only introduced concept(s), never change enrollment facts. **Progress:** P3 (preserve means unchanged phase). **Help:** O04B plus literal current task and permitted minimum context.
**Requirement IDs:** D06, D08, D12, D21, D49, D50.

**Acceptance:**
- O04B-A: each listed answer has exactly one defined next target after Continue.
- O04B-B: Back, edit, help return, unknown and failed-save behavior obey G1; original text and prior confirmed entries survive.
- O04B-C: only declared profile writes occur; picture changes obey concept prerequisites.
- O04B-D: Dynamic expands all source matches with IDs county:<FIPS>; no default. Missing lookup permits reported county/state with provenance, never fabricates crosswalk evidence.
- O04B-E: open X10 then Return/Escape restores this node’s values, draft, visible question and reading position.

### O05 · Confirm the exact supported comparison context.

**Phase / surface / wireframe:** P3 / scope / W1. **Prerequisite:** authenticated_guest_or_ephemeral.
**Required vocabulary:** contextual inline terms; no forced full lesson. Preflight and G1 apply.

**Exact proposed question:** Which coverage year are you exploring?
**Why asked / microcopy:** We will show what is available for that year and location, and keep unsupported requests visible.

| Answer / event | Visible proposed label | Confirmed next target |
|---|---|---|
| `supported` | 2027 | `O06` |
| `current` | A different year | `X04` |
| `unknown` | I am not sure | `X04` |

**Reads:** comparison.scope, capabilities.catalog. **Allowed writes:** comparison.scope.year.
**Answer effects:** `*`: Commit only declared fields from the explicit reviewed answer, with typed envelope and original text; unknown/skipped status remains distinct. Non-answer actions mutate only their named control scope..
**Agent responsibility:** Use the current task and confirmed profile to explain why this matters. Visible Edit location and category; user cannot infer nationwide data from successful ZIP lookup. Never commit an extracted fact or change the route without confirmation.
**Validation:** Use offered supported years from capability registry; 2027 is the current documented scope, not a permanent hard-coded product rule. Unknown/outside geography invokes X04 before records.
**Picture delta:** `none`; add only introduced concept(s), never change enrollment facts. **Progress:** P3 (preserve means unchanged phase). **Help:** O05 plus literal current task and permitted minimum context.
**Requirement IDs:** D06, D08, D12, D21, D49, D50.

**Acceptance:**
- O05-A: each listed answer has exactly one defined next target after Continue.
- O05-B: Back, edit, help return, unknown and failed-save behavior obey G1; original text and prior confirmed entries survive.
- O05-C: only declared profile writes occur; picture changes obey concept prerequisites.
- O05-D: Use offered supported years from capability registry; 2027 is the current documented scope, not a permanent hard-coded product rule. Unknown/outside geography invokes X04 before records.
- O05-E: open X10 then Return/Escape restores this node’s values, draft, visible question and reading position.

### O06 · Admit source-backed results before rendering.

**Phase / surface / wireframe:** P3 / catalog_loading / W11. **Prerequisite:** authenticated_guest_or_ephemeral.
**Required vocabulary:** contextual inline terms; no forced full lesson. Preflight and G1 apply.

**Exact proposed question:** Finding the available published records
**Why asked / microcopy:** A result must match the requested category, year, location and accepted source release.

| Answer / event | Visible proposed label | Confirmed next target |
|---|---|---|
| `accepted` | Accepted records available | `O07` |
| `empty` | Accepted query returned no records | `X04` |
| `pending` | Data awaiting validation | `X04` |
| `error` | Service unavailable or timed out | `X02` |
| `ambiguous_name` | Several named-plan matches | `O06B` |

**Reads:** comparison.scope, intent.compareKind, comparison.requestedNames. **Allowed writes:** comparison.snapshot.
**Answer effects:** `*`: read exact admitted response; snapshot includes scope/release/evidence; no source-admission bypass.
**Agent responsibility:** Use the current task and confirmed profile to explain why this matters. Supplement quote requests use O11 instead of manufacturing catalog rows. Never commit an extracted fact or change the route without confirmation.
**Validation:** System result only; API must enforce exact-release/claim/field gates. No placeholder plan facts in live product.
**Picture delta:** `none`; add only introduced concept(s), never change enrollment facts. **Progress:** P3 (preserve means unchanged phase). **Help:** O06 plus literal current task and permitted minimum context.
**Requirement IDs:** D22, D23, D47, D56.

**Acceptance:**
- O06-A: each listed answer has exactly one defined next target after Continue.
- O06-B: Back, edit, help return, unknown and failed-save behavior obey G1; original text and prior confirmed entries survive.
- O06-C: only declared profile writes occur; picture changes obey concept prerequisites.
- O06-D: System result only; API must enforce exact-release/claim/field gates. No placeholder plan facts in live product.
- O06-E: open X10 then Return/Escape restores this node’s values, draft, visible question and reading position.

### O06B · Resolve exact plan identity with user confirmation.

**Phase / surface / wireframe:** P3 / record_choice / W1. **Prerequisite:** authenticated_guest_or_ephemeral.
**Required vocabulary:** contextual inline terms; no forced full lesson. Preflight and G1 apply.

**Exact proposed question:** Which exact record did you mean?
**Why asked / microcopy:** Similar names can refer to different plans or years.

| Answer / event | Visible proposed label | Confirmed next target |
|---|---|---|
| `dynamic` | Select an exact plan record | `O07` |
| `unknown` | None of these / keep unresolved | `O07` |
| `edit` | Change the plan names | `O02` |

**Reads:** comparison.snapshot. **Allowed writes:** comparison.candidates.
**Answer effects:** `*`: Commit only declared fields from the explicit reviewed answer, with typed envelope and original text; unknown/skipped status remains distinct. Non-answer actions mutate only their named control scope..
**Agent responsibility:** Use the current task and confirmed profile to explain why this matters.  Never commit an extracted fact or change the route without confirmation.
**Validation:** Each dynamic option shows name, company, category, year, contract/plan/segment and geography. No first-match default.
**Picture delta:** `none`; add only introduced concept(s), never change enrollment facts. **Progress:** P3 (preserve means unchanged phase). **Help:** O06B plus literal current task and permitted minimum context.
**Requirement IDs:** D06, D08, D12, D21, D49, D50.

**Acceptance:**
- O06B-A: each listed answer has exactly one defined next target after Continue.
- O06B-B: Back, edit, help return, unknown and failed-save behavior obey G1; original text and prior confirmed entries survive.
- O06B-C: only declared profile writes occur; picture changes obey concept prerequisites.
- O06B-D: Each dynamic option shows name, company, category, year, contract/plan/segment and geography. No first-match default.
- O06B-E: open X10 then Return/Escape restores this node’s values, draft, visible question and reading position.

### O07 · Inspect useful published comparisons.

**Phase / surface / wireframe:** P3 / dashboard / W9. **Prerequisite:** authenticated_guest_or_ephemeral.
**Required vocabulary:** contextual inline terms; no forced full lesson. Preflight and G1 apply.

**Exact proposed question:** Your options and remaining checks
**Why asked / microcopy:** These facts support research. Unverified personal checks remain open.

| Answer / event | Visible proposed label | Confirmed next target |
|---|---|---|
| `save` | Save or remove a candidate | `O07` |
| `filter` | Change visible filters or sort | `O07` |
| `details` | Inspect one plan | `O08` |
| `compare` | Compare selected candidates | `O09` |
| `personal` | Add relevant personal context | `@personal_entry` |
| `continue` | Continue | `F00` |

**Reads:** comparison.snapshot, comparison.candidates, needs, coverage.current. **Allowed writes:** comparison.candidates, comparison.filters, comparison.sort.
**Answer effects:** `save`: explicit candidate add/remove command; `filter`: explicit filter/sort command; no profile fact change; `details`: read exact selected ID; `compare`: validate candidate count and mode; `personal`: set personalReview=true; `continue`: no candidate selection implied.
**Agent responsibility:** Use the current task and confirmed profile to explain why this matters. Agent walks through tradeoffs and available evidence; tools own results/order. No invented best-fit percentage or hidden exclusions. Never commit an extracted fact or change the route without confirmation.
**Validation:** Save is not enroll. Exact identity required; filter/sort explicit and reversible. Candidate selection retained with stale marker after edits. Compare requires 2–3 eligible same-role candidates, or explicit coverage-structure mode.
**Picture delta:** `reference:eligible_concepts`; add only introduced concept(s), never change enrollment facts. **Progress:** P3 (preserve means unchanged phase). **Help:** O07 plus literal current task and permitted minimum context.
**Requirement IDs:** D47, D49, D56.

**Acceptance:**
- O07-A: each listed answer has exactly one defined next target after Continue.
- O07-B: Back, edit, help return, unknown and failed-save behavior obey G1; original text and prior confirmed entries survive.
- O07-C: only declared profile writes occur; picture changes obey concept prerequisites.
- O07-D: Save is not enroll. Exact identity required; filter/sort explicit and reversible. Candidate selection retained with stale marker after edits. Compare requires 2–3 eligible same-role candidates, or explicit coverage-structure mode.
- O07-E: open X10 then Return/Escape restores this node’s values, draft, visible question and reading position.

### O08 · Show evidence for one exact record.

**Phase / surface / wireframe:** P3 / plan_detail / W9. **Prerequisite:** authenticated_guest_or_ephemeral.
**Required vocabulary:** contextual inline terms; no forced full lesson. Preflight and G1 apply.

**Exact proposed question:** Published details and personal checks
**Why asked / microcopy:** A benefit field and a personal match are different kinds of evidence.

| Answer / event | Visible proposed label | Confirmed next target |
|---|---|---|
| `save` | Save or remove this candidate | `O08` |
| `back` | Back to options | `O07` |
| `continue` | Continue | `O07` |

**Reads:** comparison.snapshot, comparison.candidates. **Allowed writes:** comparison.candidates.
**Answer effects:** `*`: Commit only declared fields from the explicit reviewed answer, with typed envelope and original text; unknown/skipped status remains distinct. Non-answer actions mutate only their named control scope..
**Agent responsibility:** Use the current task and confirmed profile to explain why this matters.  Never commit an extracted fact or change the route without confirmation.
**Validation:** Identity/year/source/units/status visible; zero differs from unknown/not applicable/conflict. Detail return retains filter, sort, page and scroll.
**Picture delta:** `none`; add only introduced concept(s), never change enrollment facts. **Progress:** P3 (preserve means unchanged phase). **Help:** O08 plus literal current task and permitted minimum context.
**Requirement IDs:** D06, D08, D12, D21, D49, D50.

**Acceptance:**
- O08-A: each listed answer has exactly one defined next target after Continue.
- O08-B: Back, edit, help return, unknown and failed-save behavior obey G1; original text and prior confirmed entries survive.
- O08-C: only declared profile writes occur; picture changes obey concept prerequisites.
- O08-D: Identity/year/source/units/status visible; zero differs from unknown/not applicable/conflict. Detail return retains filter, sort, page and scroll.
- O08-E: open X10 then Return/Escape restores this node’s values, draft, visible question and reading position.

### O09 · Compare consistent dimensions side by side.

**Phase / surface / wireframe:** P3 / comparison / W10. **Prerequisite:** authenticated_guest_or_ephemeral.
**Required vocabulary:** premium, care_cost. Preflight and G1 apply.

**Exact proposed question:** Compare the selected candidates
**Why asked / microcopy:** Each column uses the same dimensions. Missing facts remain visible.

| Answer / event | Visible proposed label | Confirmed next target |
|---|---|---|
| `edit` | Change candidates | `O07` |
| `choose` | Record my preference | `O10` |
| `continue` | Continue with checks open | `F00` |

**Reads:** comparison.candidates, comparison.snapshot, coverage.current. **Allowed writes:** comparison.viewedSnapshot.
**Answer effects:** `*`: Commit only declared fields from the explicit reviewed answer, with typed envelope and original text; unknown/skipped status remains distinct. Non-answer actions mutate only their named control scope..
**Agent responsibility:** Use the current task and confirmed profile to explain why this matters. Contextual Ask Daylight can explain a row or ask about a tradeoff without changing order or preference. Never commit an extracted fact or change the route without confirmation.
**Validation:** Do not compare a PDP premium to total Original Medicare costs. Same-role plan mode or explicit structure/bundle mode only; unsupported bundle totals show component unknowns. Stale comparison blocks preference confirmation until refresh.
**Picture delta:** `reference:eligible_concepts`; add only introduced concept(s), never change enrollment facts. **Progress:** P3 (preserve means unchanged phase). **Help:** O09 plus literal current task and permitted minimum context.
**Requirement IDs:** D06, D08, D12, D21, D49, D50.

**Acceptance:**
- O09-A: each listed answer has exactly one defined next target after Continue.
- O09-B: Back, edit, help return, unknown and failed-save behavior obey G1; original text and prior confirmed entries survive.
- O09-C: only declared profile writes occur; picture changes obey concept prerequisites.
- O09-D: Do not compare a PDP premium to total Original Medicare costs. Same-role plan mode or explicit structure/bundle mode only; unsupported bundle totals show component unknowns. Stale comparison blocks preference confirmation until refresh.
- O09-E: open X10 then Return/Escape restores this node’s values, draft, visible question and reading position.

### O10 · Record the person’s own research preference.

**Phase / surface / wireframe:** P3 / preference_confirmation / W10. **Prerequisite:** authenticated_guest_or_ephemeral.
**Required vocabulary:** contextual inline terms; no forced full lesson. Preflight and G1 apply.

**Exact proposed question:** What would you like to keep as your current preference?
**Why asked / microcopy:** This records your thinking. It does not enroll you or cancel existing coverage.

| Answer / event | Visible proposed label | Confirmed next target |
|---|---|---|
| `candidate` | A selected candidate | `F00` |
| `keep` | Keep my current coverage for now | `F00` |
| `undecided` | I am still deciding | `F00` |
| `checks` | Check unresolved facts before deciding | `F00` |

**Reads:** comparison.candidates, coverage.current, checks. **Allowed writes:** intent.statedPreference.
**Answer effects:** `candidate`: statedPreference=explicit current candidate ID, snapshot and open checks; `keep`: statedPreference=keep_current, reported; `undecided`: statedPreference=undecided; `checks`: statedPreference=verify_first.
**Agent responsibility:** Use the current task and confirmed profile to explain why this matters.  Never commit an extracted fact or change the route without confirmation.
**Validation:** Dynamic candidate IDs must match current accepted snapshot; no default. Summarize material unresolved checks beside confirmation. Never label decision-ready when prerequisites missing.
**Picture delta:** `none`; add only introduced concept(s), never change enrollment facts. **Progress:** P3 (preserve means unchanged phase). **Help:** O10 plus literal current task and permitted minimum context.
**Requirement IDs:** D06, D08, D12, D21, D49, D50.

**Acceptance:**
- O10-A: each listed answer has exactly one defined next target after Continue.
- O10-B: Back, edit, help return, unknown and failed-save behavior obey G1; original text and prior confirmed entries survive.
- O10-C: only declared profile writes occur; picture changes obey concept prerequisites.
- O10-D: Dynamic candidate IDs must match current accepted snapshot; no default. Summarize material unresolved checks beside confirmation. Never label decision-ready when prerequisites missing.
- O10-E: open X10 then Return/Escape restores this node’s values, draft, visible question and reading position.

### O11 · Provide supplement education without a fabricated insurer quote.

**Phase / surface / wireframe:** P3 / unsupported_quote / W11. **Prerequisite:** authenticated_guest_or_ephemeral.
**Required vocabulary:** contextual inline terms; no forced full lesson. Preflight and G1 apply.

**Exact proposed question:** Compare standardized supplement benefits
**Why asked / microcopy:** Published benefit education is available; personal insurer prices and buying rights need separate checks.

| Answer / event | Visible proposed label | Confirmed next target |
|---|---|---|
| `rights` | Help me check timing questions | `C07` |
| `prepare` | Prepare supplement questions | `F01` |
| `other_options` | Explore other coverage options | `O00` |
| `continue` | Continue | `F00` |

**Reads:** coverage.current, coverage.partBStart, capabilities.medigap. **Allowed writes:** checks.supplement.
**Answer effects:** `*`: Commit only declared fields from the explicit reviewed answer, with typed envelope and original text; unknown/skipped status remains distinct. Non-answer actions mutate only their named control scope..
**Agent responsibility:** Use the current task and confirmed profile to explain why this matters.  Never commit an extracted fact or change the route without confirmation.
**Validation:** Benefits chart only where reviewed; any illustrative state rates separately labeled with date/assumptions, never a personal quote. No nationwide standardization assumption.
**Picture delta:** `reference:medigap`; add only introduced concept(s), never change enrollment facts. **Progress:** P3 (preserve means unchanged phase). **Help:** O11 plus literal current task and permitted minimum context.
**Requirement IDs:** D06, D08, D12, D21, D49, D50.

**Acceptance:**
- O11-A: each listed answer has exactly one defined next target after Continue.
- O11-B: Back, edit, help return, unknown and failed-save behavior obey G1; original text and prior confirmed entries survive.
- O11-C: only declared profile writes occur; picture changes obey concept prerequisites.
- O11-D: Benefits chart only where reviewed; any illustrative state rates separately labeled with date/assumptions, never a personal quote. No nationwide standardization assumption.
- O11-E: open X10 then Return/Escape restores this node’s values, draft, visible question and reading position.

### F00 · Give one relevant next action and an honest summary.

**Phase / surface / wireframe:** P4 / summary / W13. **Prerequisite:** authenticated_guest_or_ephemeral.
**Required vocabulary:** contextual inline terms; no forced full lesson. Preflight and G1 apply.

**Exact proposed question:** Your next step
**Why asked / microcopy:** Here is what you reported, what we could check, and what remains open.

| Answer / event | Visible proposed label | Confirmed next target |
|---|---|---|
| `prepare` | Help me prepare this step | `F01` |
| `learning` | Continue learning | `L01` |
| `options` | Revisit options | `O07` |
| `finish` | Keep my guide for later | `F03` |

**Reads:** intent, coverage, needs, comparison, checks, privacy. **Allowed writes:** outcome.status, outcome.nextTask.
**Answer effects:** `*`: Commit only declared fields from the explicit reviewed answer, with typed envelope and original text; unknown/skipped status remains distinct. Non-answer actions mutate only their named control scope..
**Agent responsibility:** Use the current task and confirmed profile to explain why this matters. Education-only summary has no forced shopping action. Job route groups employer/enrollment/replacement checks. Keep current remains valid. Never commit an extracted fact or change the route without confirmation. Next-task rule: unresolved transition/enrollment coordination first when relevant; then unverified replacement rights; then user-prioritized provider/drug checks; else learning/review summary. This is a review-priority order, not a computed legal deadline.
**Validation:** Only route-relevant actions shown; O07 action returns O00 when no current snapshot. One primary suggested next step selected by deterministic task rules. All original notes retained.
**Picture delta:** `reference:eligible_concepts`; add only introduced concept(s), never change enrollment facts. **Progress:** P4 (preserve means unchanged phase). **Help:** F00 plus literal current task and permitted minimum context.
**Requirement IDs:** D21, D48, D49, D56.

**Acceptance:**
- F00-A: each listed answer has exactly one defined next target after Continue.
- F00-B: Back, edit, help return, unknown and failed-save behavior obey G1; original text and prior confirmed entries survive.
- F00-C: only declared profile writes occur; picture changes obey concept prerequisites.
- F00-D: Only route-relevant actions shown; O07 action returns O00 when no current snapshot. One primary suggested next step selected by deterministic task rules. All original notes retained.
- F00-E: open X10 then Return/Escape restores this node’s values, draft, visible question and reading position.

### F01 · Prepare a useful editable output.

**Phase / surface / wireframe:** P4 / preparation / W13. **Prerequisite:** authenticated_guest_or_ephemeral.
**Required vocabulary:** contextual inline terms; no forced full lesson. Preflight and G1 apply.

**Exact proposed question:** Prepare questions, a script or a checklist
**Why asked / microcopy:** This draft has not been sent to anyone.

| Answer / event | Visible proposed label | Confirmed next target |
|---|---|---|
| `edit` | Edit the draft | `F01` |
| `copy` | Copy the draft | `F01` |
| `print` | Print or save a copy | `F02` |
| `handoff` | Review available human help | `H00` |
| `continue` | Continue | `F00` |

**Reads:** outcome.nextTask, coverage, needs, checks. **Allowed writes:** outcome.drafts.
**Answer effects:** `*`: Commit only declared fields from the explicit reviewed answer, with typed envelope and original text; unknown/skipped status remains distinct. Non-answer actions mutate only their named control scope..
**Agent responsibility:** Use the current task and confirmed profile to explain why this matters.  Never commit an extracted fact or change the route without confirmation.
**Validation:** Template selected by task; text editable; unknowns explicit; no invented phone number/person/service. Store draft versions and flag context changes. User text is data, never agent instructions.
**Picture delta:** `none`; add only introduced concept(s), never change enrollment facts. **Progress:** P4 (preserve means unchanged phase). **Help:** F01 plus literal current task and permitted minimum context.
**Requirement IDs:** D06, D08, D12, D21, D49, D50.

**Acceptance:**
- F01-A: each listed answer has exactly one defined next target after Continue.
- F01-B: Back, edit, help return, unknown and failed-save behavior obey G1; original text and prior confirmed entries survive.
- F01-C: only declared profile writes occur; picture changes obey concept prerequisites.
- F01-D: Template selected by task; text editable; unknowns explicit; no invented phone number/person/service. Store draft versions and flag context changes. User text is data, never agent instructions.
- F01-E: open X10 then Return/Escape restores this node’s values, draft, visible question and reading position.

### F02 · Keep screen and exported summary consistent.

**Phase / surface / wireframe:** P4 / print / W13. **Prerequisite:** authenticated_guest_or_ephemeral.
**Required vocabulary:** contextual inline terms; no forced full lesson. Preflight and G1 apply.

**Exact proposed question:** Review your printable guide
**Why asked / microcopy:** The copy includes its date, reported facts, sources, open checks, notes and edited drafts.

| Answer / event | Visible proposed label | Confirmed next target |
|---|---|---|
| `print` | Print or save PDF | `F02` |
| `return` | Return to my next step | `F00` |

**Reads:** outcome, coverage, needs, comparison, checks. **Allowed writes:** outcome.lastPrintAt.
**Answer effects:** `*`: Commit only declared fields from the explicit reviewed answer, with typed envelope and original text; unknown/skipped status remains distinct. Non-answer actions mutate only their named control scope..
**Agent responsibility:** Use the current task and confirmed profile to explain why this matters.  Never commit an extracted fact or change the route without confirmation.
**Validation:** Use same summary model; readable multi-page output allowed; no duplicate numbering or universal deadline. Cancel print leaves state unchanged.
**Picture delta:** `none`; add only introduced concept(s), never change enrollment facts. **Progress:** P4 (preserve means unchanged phase). **Help:** F02 plus literal current task and permitted minimum context.
**Requirement IDs:** D06, D08, D12, D21, D49, D50.

**Acceptance:**
- F02-A: each listed answer has exactly one defined next target after Continue.
- F02-B: Back, edit, help return, unknown and failed-save behavior obey G1; original text and prior confirmed entries survive.
- F02-C: only declared profile writes occur; picture changes obey concept prerequisites.
- F02-D: Use same summary model; readable multi-page output allowed; no duplicate numbering or universal deadline. Cancel print leaves state unchanged.
- F02-E: open X10 then Return/Escape restores this node’s values, draft, visible question and reading position.

### F03 · State actual save status and safe departure options.

**Phase / surface / wireframe:** P4 / finish / W12. **Prerequisite:** authenticated_guest_or_ephemeral.
**Required vocabulary:** contextual inline terms; no forced full lesson. Preflight and G1 apply.

**Exact proposed question:** Your guide is ready to revisit
**Why asked / microcopy:** Saved means the backend acknowledged the latest version. Visit-only work may be lost when this session ends.

| Answer / event | Visible proposed label | Confirmed next target |
|---|---|---|
| `save` | Keep saved on this browser | `F03` |
| `forget` | Finish and remove this browser’s access | `X06` |
| `delete` | Delete my saved guide | `X07` |
| `return` | Return to next steps | `F00` |

**Reads:** privacy.persistenceChoice, sync.status. **Allowed writes:** outcome.finishedAt.
**Answer effects:** `*`: Commit only declared fields from the explicit reviewed answer, with typed envelope and original text; unknown/skipped status remains distinct. Non-answer actions mutate only their named control scope..
**Agent responsibility:** Use the current task and confirmed profile to explain why this matters.  Never commit an extracted fact or change the route without confirmation.
**Validation:** No Saved label before acknowledgement. Removing browser access is distinct from server deletion; explain orphaned guest recovery limitations.
**Picture delta:** `none`; add only introduced concept(s), never change enrollment facts. **Progress:** P4 (preserve means unchanged phase). **Help:** F03 plus literal current task and permitted minimum context.
**Requirement IDs:** D06, D08, D12, D21, D49, D50.

**Acceptance:**
- F03-A: each listed answer has exactly one defined next target after Continue.
- F03-B: Back, edit, help return, unknown and failed-save behavior obey G1; original text and prior confirmed entries survive.
- F03-C: only declared profile writes occur; picture changes obey concept prerequisites.
- F03-D: No Saved label before acknowledgement. Removing browser access is distinct from server deletion; explain orphaned guest recovery limitations.
- F03-E: open X10 then Return/Escape restores this node’s values, draft, visible question and reading position.

### H00 · Offer only an actual supported human destination.

**Phase / surface / wireframe:** P4 / handoff / W13. **Prerequisite:** authenticated_guest_or_ephemeral.
**Required vocabulary:** contextual inline terms; no forced full lesson. Preflight and G1 apply.

**Exact proposed question:** Would you like help reviewing the next step?
**Why asked / microcopy:** We will show who receives information and what they can actually do before sharing anything.

| Answer / event | Visible proposed label | Confirmed next target |
|---|---|---|
| `official` | Use an official counseling or Medicare resource | `F00` |
| `prepare` | Prepare a message myself | `F01` |
| `request` | Review an available licensed handoff | `H01` |
| `skip` | Continue without sharing | `F00` |

**Reads:** capabilities.handoff, checks. **Allowed writes:** outcome.handoffIntent.
**Answer effects:** `*`: Commit only declared fields from the explicit reviewed answer, with typed envelope and original text; unknown/skipped status remains distinct. Non-answer actions mutate only their named control scope..
**Agent responsibility:** Use the current task and confirmed profile to explain why this matters. No outbound action is authorized by this design task. Never commit an extracted fact or change the route without confirmation.
**Validation:** Request action absent/disabled with explanation when no qualified operator integration is available. Official links are not a Daylight service promise.
**Picture delta:** `none`; add only introduced concept(s), never change enrollment facts. **Progress:** P4 (preserve means unchanged phase). **Help:** H00 plus literal current task and permitted minimum context.
**Requirement IDs:** D22, D23, D48, D56.

**Acceptance:**
- H00-A: each listed answer has exactly one defined next target after Continue.
- H00-B: Back, edit, help return, unknown and failed-save behavior obey G1; original text and prior confirmed entries survive.
- H00-C: only declared profile writes occur; picture changes obey concept prerequisites.
- H00-D: Request action absent/disabled with explanation when no qualified operator integration is available. Official links are not a Daylight service promise.
- H00-E: open X10 then Return/Escape restores this node’s values, draft, visible question and reading position.

### H01 · Review minimum context and recipient before a future share.

**Phase / surface / wireframe:** P4 / handoff_review / W13. **Prerequisite:** authenticated_guest_or_ephemeral.
**Required vocabulary:** contextual inline terms; no forced full lesson. Preflight and G1 apply.

**Exact proposed question:** Review this handoff before anything is sent
**Why asked / microcopy:** Review the recipient, purpose, included fields, message, availability and expected response.

| Answer / event | Visible proposed label | Confirmed next target |
|---|---|---|
| `approve` | Approve this exact handoff | `H02` |
| `edit` | Edit what would be shared | `H01` |
| `cancel` | Do not share | `F00` |

**Reads:** capabilities.handoff, outcome.handoffDraft, privacy. **Allowed writes:** consent.handoff.
**Answer effects:** `*`: Commit only declared fields from the explicit reviewed answer, with typed envelope and original text; unknown/skipped status remains distinct. Non-answer actions mutate only their named control scope..
**Agent responsibility:** Use the current task and confirmed profile to explain why this matters.  Never commit an extracted fact or change the route without confirmation.
**Validation:** Future gated capability only. Separate explicit authorization for exact recipient/payload; caregiver role not authority; no automatic enrollment/cancellation.
**Picture delta:** `none`; add only introduced concept(s), never change enrollment facts. **Progress:** P4 (preserve means unchanged phase). **Help:** H01 plus literal current task and permitted minimum context.
**Requirement IDs:** D06, D08, D12, D21, D49, D50.

**Acceptance:**
- H01-A: each listed answer has exactly one defined next target after Continue.
- H01-B: Back, edit, help return, unknown and failed-save behavior obey G1; original text and prior confirmed entries survive.
- H01-C: only declared profile writes occur; picture changes obey concept prerequisites.
- H01-D: Future gated capability only. Separate explicit authorization for exact recipient/payload; caregiver role not authority; no automatic enrollment/cancellation.
- H01-E: open X10 then Return/Escape restores this node’s values, draft, visible question and reading position.

### H02 · Track real delivery milestones.

**Phase / surface / wireframe:** P4 / handoff_status / W13. **Prerequisite:** authenticated_guest_or_ephemeral.
**Required vocabulary:** contextual inline terms; no forced full lesson. Preflight and G1 apply.

**Exact proposed question:** Handoff status
**Why asked / microcopy:** Requested, sent, acknowledged, scheduled, and completed mean different things.

| Answer / event | Visible proposed label | Confirmed next target |
|---|---|---|
| `receipt` | Delivery acknowledged | `F00` |
| `pending` | Still pending | `H02` |
| `failed` | Not sent / failed | `H01` |
| `uncertain` | Delivery outcome uncertain | `X03` |
| `cancel` | Cancel a pending request if supported | `H02` |

**Reads:** outcome.handoffReceipt. **Allowed writes:** outcome.handoffStatus.
**Answer effects:** `*`: Commit only declared fields from the explicit reviewed answer, with typed envelope and original text; unknown/skipped status remains distinct. Non-answer actions mutate only their named control scope..
**Agent responsibility:** Use the current task and confirmed profile to explain why this matters.  Never commit an extracted fact or change the route without confirmation.
**Validation:** System events require receipts; uncertain send checked by idempotency key before retry. Do not promise cancellation after confirmed delivery.
**Picture delta:** `none`; add only introduced concept(s), never change enrollment facts. **Progress:** P4 (preserve means unchanged phase). **Help:** H02 plus literal current task and permitted minimum context.
**Requirement IDs:** D06, D08, D12, D21, D49, D50.

**Acceptance:**
- H02-A: each listed answer has exactly one defined next target after Continue.
- H02-B: Back, edit, help return, unknown and failed-save behavior obey G1; original text and prior confirmed entries survive.
- H02-C: only declared profile writes occur; picture changes obey concept prerequisites.
- H02-D: System events require receipts; uncertain send checked by idempotency key before retry. Do not promise cancellation after confirmed delivery.
- H02-E: open X10 then Return/Escape restores this node’s values, draft, visible question and reading position.

### X01 · Confirm extracted or ambiguous information before it affects the guide.

**Phase / surface / wireframe:** preserve / confirmation_overlay / W4. **Prerequisite:** authenticated_guest_or_ephemeral.
**Required vocabulary:** contextual inline terms; no forced full lesson. Preflight and G1 apply.

**Exact proposed question:** Did Daylight understand you correctly?
**Why asked / microcopy:** Your original words stay available. You can correct or decline the interpretation.

| Answer / event | Visible proposed label | Confirmed next target |
|---|---|---|
| `accept` | Confirm these details | `@confirmed_return` |
| `edit` | Edit the proposed details | `X01` |
| `unknown` | Keep unresolved details unknown | `@unknown_return` |
| `cancel` | Return without changes | `@origin` |

**Reads:** flow.origin, drafts.raw, drafts.proposed, profile.version. **Allowed writes:** confirmed_patch, history.event.
**Answer effects:** `accept`: apply only reviewed typed allowlisted patch with expectedVersion/idempotency; `edit`: modify proposed values only; `unknown`: save raw in allowed scope; unsupported fields stay unknown; dispatch known safe branch; `cancel`: discard unconfirmed proposal; preserve raw draft for user review.
**Agent responsibility:** Use the current task and confirmed profile to explain why this matters. For knowledge propose starting depth; for goal propose one of four; for other answers propose known supported values. No generated insurance rule. Multiple facts can be confirmed together. Never commit an extracted fact or change the route without confirmation.
**Validation:** Allowlisted typed patch only; show raw text and per-field value/status. Check expectedVersion and provenance. Incompatible facts stay pending; no silent overwrites.
**Picture delta:** `none`; add only introduced concept(s), never change enrollment facts. **Progress:** preserve (preserve means unchanged phase). **Help:** X01 plus literal current task and permitted minimum context.
**Requirement IDs:** D12, D22, D49, D50, D52.

**Acceptance:**
- X01-A: each listed answer has exactly one defined next target after Continue.
- X01-B: Back, edit, help return, unknown and failed-save behavior obey G1; original text and prior confirmed entries survive.
- X01-C: only declared profile writes occur; picture changes obey concept prerequisites.
- X01-D: Allowlisted typed patch only; show raw text and per-field value/status. Check expectedVersion and provenance. Incompatible facts stay pending; no silent overwrites.
- X01-E: open X10 then Return/Escape restores this node’s values, draft, visible question and reading position.

### X02 · Recover from unavailable model, network or backend.

**Phase / surface / wireframe:** preserve / error_overlay / W11. **Prerequisite:** authenticated_guest_or_ephemeral.
**Required vocabulary:** contextual inline terms; no forced full lesson. Preflight and G1 apply.

**Exact proposed question:** We could not complete that request
**Why asked / microcopy:** Your entered text stays here. We will show what has and has not been saved.

| Answer / event | Visible proposed label | Confirmed next target |
|---|---|---|
| `retry` | Retry the same request | `@origin` |
| `local` | Continue with available guide explanations | `@safe_local` |
| `return` | Return to the question | `@origin` |

**Reads:** flow.origin, sync.status, capabilities. **Allowed writes:** errors.last.
**Answer effects:** `*`: Commit only declared fields from the explicit reviewed answer, with typed envelope and original text; unknown/skipped status remains distinct. Non-answer actions mutate only their named control scope..
**Agent responsibility:** Use the current task and confirmed profile to explain why this matters.  Never commit an extracted fact or change the route without confirmation.
**Validation:** Model failure never replaces an unknown with no. Retry bounded and idempotent. Storage failure leaves local pending state clearly unsaved; do not silently switch persistence mode.
**Picture delta:** `none`; add only introduced concept(s), never change enrollment facts. **Progress:** preserve (preserve means unchanged phase). **Help:** X02 plus literal current task and permitted minimum context.
**Requirement IDs:** D06, D08, D12, D21, D49, D50.

**Acceptance:**
- X02-A: each listed answer has exactly one defined next target after Continue.
- X02-B: Back, edit, help return, unknown and failed-save behavior obey G1; original text and prior confirmed entries survive.
- X02-C: only declared profile writes occur; picture changes obey concept prerequisites.
- X02-D: Model failure never replaces an unknown with no. Retry bounded and idempotent. Storage failure leaves local pending state clearly unsaved; do not silently switch persistence mode.
- X02-E: open X10 then Return/Escape restores this node’s values, draft, visible question and reading position.

### X03 · Resolve version conflicts or uncertain mutations.

**Phase / surface / wireframe:** preserve / conflict_overlay / W11. **Prerequisite:** authenticated_guest_or_ephemeral.
**Required vocabulary:** contextual inline terms; no forced full lesson. Preflight and G1 apply.

**Exact proposed question:** Your guide changed before this update finished
**Why asked / microcopy:** We kept both versions for review. Nothing will be overwritten silently.

| Answer / event | Visible proposed label | Confirmed next target |
|---|---|---|
| `reload` | Review the latest saved version | `@origin` |
| `merge` | Review my changes against it | `X01` |
| `discard` | Keep the saved version | `@origin` |

**Reads:** profile.version, sync.pendingOperation. **Allowed writes:** sync.conflict.
**Answer effects:** `*`: Commit only declared fields from the explicit reviewed answer, with typed envelope and original text; unknown/skipped status remains distinct. Non-answer actions mutate only their named control scope..
**Agent responsibility:** Use the current task and confirmed profile to explain why this matters.  Never commit an extracted fact or change the route without confirmation.
**Validation:** Fetch authenticated latest version; per-field conflict resolution. Uncertain operations query receipt by key before replay.
**Picture delta:** `none`; add only introduced concept(s), never change enrollment facts. **Progress:** preserve (preserve means unchanged phase). **Help:** X03 plus literal current task and permitted minimum context.
**Requirement IDs:** D06, D08, D12, D21, D49, D50.

**Acceptance:**
- X03-A: each listed answer has exactly one defined next target after Continue.
- X03-B: Back, edit, help return, unknown and failed-save behavior obey G1; original text and prior confirmed entries survive.
- X03-C: only declared profile writes occur; picture changes obey concept prerequisites.
- X03-D: Fetch authenticated latest version; per-field conflict resolution. Uncertain operations query receipt by key before replay.
- X03-E: open X10 then Return/Escape restores this node’s values, draft, visible question and reading position.

### X04 · Offer useful alternatives for unsupported scope or evidence.

**Phase / surface / wireframe:** preserve / unsupported / W11. **Prerequisite:** authenticated_guest_or_ephemeral.
**Required vocabulary:** contextual inline terms; no forced full lesson. Preflight and G1 apply.

**Exact proposed question:** This comparison is not available here yet
**Why asked / microcopy:** The guide can still help you learn and prepare questions. We will not substitute another location, year or unreviewed data.

| Answer / event | Visible proposed label | Confirmed next target |
|---|---|---|
| `edit` | Change comparison context | `O00` |
| `official` | Open official comparison resources | `F00` |
| `prepare` | Prepare questions with this request retained | `F01` |
| `learn` | Continue learning | `L01` |

**Reads:** comparison.scope, capabilities, checks. **Allowed writes:** checks.unsupportedScope.
**Answer effects:** `*`: Commit only declared fields from the explicit reviewed answer, with typed envelope and original text; unknown/skipped status remains distinct. Non-answer actions mutate only their named control scope..
**Agent responsibility:** Use the current task and confirmed profile to explain why this matters.  Never commit an extracted fact or change the route without confirmation.
**Validation:** Preserve exact requested context and prior candidates as stale reference. Unknown geography is not outside. Link label identifies destination.
**Picture delta:** `none`; add only introduced concept(s), never change enrollment facts. **Progress:** preserve (preserve means unchanged phase). **Help:** X04 plus literal current task and permitted minimum context.
**Requirement IDs:** D06, D08, D12, D21, D49, D50.

**Acceptance:**
- X04-A: each listed answer has exactly one defined next target after Continue.
- X04-B: Back, edit, help return, unknown and failed-save behavior obey G1; original text and prior confirmed entries survive.
- X04-C: only declared profile writes occur; picture changes obey concept prerequisites.
- X04-D: Preserve exact requested context and prior candidates as stale reference. Unknown geography is not outside. Link label identifies destination.
- X04-E: open X10 then Return/Escape restores this node’s values, draft, visible question and reading position.

### X05 · Resume safely on the same browser.

**Phase / surface / wireframe:** P1 / resume / W12. **Prerequisite:** authenticated_guest_or_ephemeral.
**Required vocabulary:** contextual inline terms; no forced full lesson. Preflight and G1 apply.

**Exact proposed question:** Resume your saved guide?
**Why asked / microcopy:** This device can reopen a guest guide. Confirm it is the guide you want before showing sensitive details.

| Answer / event | Visible proposed label | Confirmed next target |
|---|---|---|
| `resume` | Resume this guide | `@resume` |
| `private` | Start a separate visit without changing the saved guide | `A01` |
| `manage` | Manage saved information | `X06` |

**Reads:** session.cookie, profile.version. **Allowed writes:** session.active.
**Answer effects:** `*`: Commit only declared fields from the explicit reviewed answer, with typed envelope and original text; unknown/skipped status remains distinct. Non-answer actions mutate only their named control scope..
**Agent responsibility:** Use the current task and confirmed profile to explain why this matters.  Never commit an extracted fact or change the route without confirmation.
**Validation:** Same-browser authenticated cookie only; masked summary before reveal. Expired/missing session gets clear no-recovery message and new visit. No public bearer link or name-based lookup.
**Picture delta:** `none`; add only introduced concept(s), never change enrollment facts. **Progress:** P1 (preserve means unchanged phase). **Help:** X05 plus literal current task and permitted minimum context.
**Requirement IDs:** D06, D08, D12, D21, D49, D50.

**Acceptance:**
- X05-A: each listed answer has exactly one defined next target after Continue.
- X05-B: Back, edit, help return, unknown and failed-save behavior obey G1; original text and prior confirmed entries survive.
- X05-C: only declared profile writes occur; picture changes obey concept prerequisites.
- X05-D: Same-browser authenticated cookie only; masked summary before reveal. Expired/missing session gets clear no-recovery message and new visit. No public bearer link or name-based lookup.
- X05-E: open X10 then Return/Escape restores this node’s values, draft, visible question and reading position.

### X06 · Review data choices and shared-device consequences.

**Phase / surface / wireframe:** preserve / privacy_panel / W12. **Prerequisite:** authenticated_guest_or_ephemeral.
**Required vocabulary:** contextual inline terms; no forced full lesson. Preflight and G1 apply.

**Exact proposed question:** Your saved information
**Why asked / microcopy:** Review what is saved, what is sent to AI, and how to remove this browser’s access or delete the guide.

| Answer / event | Visible proposed label | Confirmed next target |
|---|---|---|
| `return` | Return to where I was | `@origin` |
| `visit` | Use only this visit from here | `@origin` |
| `sensitive` | Change medicine and provider saving | `X08` |
| `forget` | Remove this browser’s access | `X09` |
| `delete` | Delete my saved guide | `X07` |

**Reads:** privacy, session, profile.summary. **Allowed writes:** privacy.preferences.
**Answer effects:** `*`: Commit only declared fields from the explicit reviewed answer, with typed envelope and original text; unknown/skipped status remains distinct. Non-answer actions mutate only their named control scope..
**Agent responsibility:** Use the current task and confirmed profile to explain why this matters.  Never commit an extracted fact or change the route without confirmation.
**Validation:** Changing future persistence does not imply old server data deleted. Show separate delete action; retention values must be approved configuration, not invented.
**Picture delta:** `none`; add only introduced concept(s), never change enrollment facts. **Progress:** preserve (preserve means unchanged phase). **Help:** X06 plus literal current task and permitted minimum context.
**Requirement IDs:** D06, D08, D12, D21, D49, D50.

**Acceptance:**
- X06-A: each listed answer has exactly one defined next target after Continue.
- X06-B: Back, edit, help return, unknown and failed-save behavior obey G1; original text and prior confirmed entries survive.
- X06-C: only declared profile writes occur; picture changes obey concept prerequisites.
- X06-D: Changing future persistence does not imply old server data deleted. Show separate delete action; retention values must be approved configuration, not invented.
- X06-E: open X10 then Return/Escape restores this node’s values, draft, visible question and reading position.

### X07 · Make destructive scope explicit.

**Phase / surface / wireframe:** preserve / delete_confirmation / W12. **Prerequisite:** authenticated_guest_or_ephemeral.
**Required vocabulary:** contextual inline terms; no forced full lesson. Preflight and G1 apply.

**Exact proposed question:** Delete this saved guest guide?
**Why asked / microcopy:** This removes access now and starts the stated deletion process for saved profile content. The notice explains backup or legally required retention separately.

| Answer / event | Visible proposed label | Confirmed next target |
|---|---|---|
| `delete` | Delete this guide | `X09` |
| `cancel` | Keep my guide | `@origin` |

**Reads:** profile.id, privacy.retentionPolicy. **Allowed writes:** deletion.request.
**Answer effects:** `delete`: request explicitly scoped deletion; wait for real receipt; `cancel`: no destructive mutation.
**Agent responsibility:** Use the current task and confirmed profile to explain why this matters.  Never commit an extracted fact or change the route without confirmation.
**Validation:** Initial focus Keep. Delete requires current guest authorization, CSRF protection and idempotency; await receipt. Failed/uncertain deletion uses X02/X03, not a success message.
**Picture delta:** `none`; add only introduced concept(s), never change enrollment facts. **Progress:** preserve (preserve means unchanged phase). **Help:** X07 plus literal current task and permitted minimum context.
**Requirement IDs:** D06, D08, D12, D21, D49, D50.

**Acceptance:**
- X07-A: each listed answer has exactly one defined next target after Continue.
- X07-B: Back, edit, help return, unknown and failed-save behavior obey G1; original text and prior confirmed entries survive.
- X07-C: only declared profile writes occur; picture changes obey concept prerequisites.
- X07-D: Initial focus Keep. Delete requires current guest authorization, CSRF protection and idempotency; await receipt. Failed/uncertain deletion uses X02/X03, not a success message.
- X07-E: open X10 then Return/Escape restores this node’s values, draft, visible question and reading position.

### X08 · Control optional durable sensitive data.

**Phase / surface / wireframe:** preserve / sensitive_notice / W12. **Prerequisite:** authenticated_guest_or_ephemeral.
**Required vocabulary:** contextual inline terms; no forced full lesson. Preflight and G1 apply.

**Exact proposed question:** Save medicine and provider details for another visit?
**Why asked / microcopy:** These details can reveal health information. You can use them only for this visit or save them with the guest guide.

| Answer / event | Visible proposed label | Confirmed next target |
|---|---|---|
| `save` | Save the reviewed details | `@origin` |
| `visit` | Use details only for this visit | `@origin` |
| `remove` | Remove previously saved details | `X07` |

**Reads:** privacy, needs. **Allowed writes:** privacy.sensitiveChoice.
**Answer effects:** `save`: grant durable-save scope only for reviewed selected categories; no AI disclosure grant; `visit`: keep sensitive fields in memory; no durable history/cache copy; `remove`: set deletion scope to sensitive categories then request confirmation.
**Agent responsibility:** Use the current task and confirmed profile to explain why this matters.  Never commit an extracted fact or change the route without confirmation.
**Validation:** No preselection; optional per-category scope. Remove uses a scoped deletion confirmation, not whole-profile deletion. AI transfer remains a separate choice.
**Picture delta:** `none`; add only introduced concept(s), never change enrollment facts. **Progress:** preserve (preserve means unchanged phase). **Help:** X08 plus literal current task and permitted minimum context.
**Requirement IDs:** D06, D08, D12, D21, D49, D50.

**Acceptance:**
- X08-A: each listed answer has exactly one defined next target after Continue.
- X08-B: Back, edit, help return, unknown and failed-save behavior obey G1; original text and prior confirmed entries survive.
- X08-C: only declared profile writes occur; picture changes obey concept prerequisites.
- X08-D: No preselection; optional per-category scope. Remove uses a scoped deletion confirmation, not whole-profile deletion. AI transfer remains a separate choice.
- X08-E: open X10 then Return/Escape restores this node’s values, draft, visible question and reading position.

### X09 · Report actual access or deletion outcome.

**Phase / surface / wireframe:** P1 / session_result / W12. **Prerequisite:** authenticated_guest_or_ephemeral.
**Required vocabulary:** contextual inline terms; no forced full lesson. Preflight and G1 apply.

**Exact proposed question:** This browser’s access has been removed
**Why asked / microcopy:** If you deleted data, the result shows what was removed and any stated retention limits.

| Answer / event | Visible proposed label | Confirmed next target |
|---|---|---|
| `new` | Start a new guide | `A00` |

**Reads:** deletion.receipt, session. **Allowed writes:** session.status.
**Answer effects:** `*`: Commit only declared fields from the explicit reviewed answer, with typed envelope and original text; unknown/skipped status remains distinct. Non-answer actions mutate only their named control scope..
**Agent responsibility:** Use the current task and confirmed profile to explain why this matters.  Never commit an extracted fact or change the route without confirmation.
**Validation:** Only render success text matching actual acknowledged operation; forgetting cookie alone is not server deletion.
**Picture delta:** `none`; add only introduced concept(s), never change enrollment facts. **Progress:** P1 (preserve means unchanged phase). **Help:** X09 plus literal current task and permitted minimum context.
**Requirement IDs:** D06, D08, D12, D21, D49, D50.

**Acceptance:**
- X09-A: each listed answer has exactly one defined next target after Continue.
- X09-B: Back, edit, help return, unknown and failed-save behavior obey G1; original text and prior confirmed entries survive.
- X09-C: only declared profile writes occur; picture changes obey concept prerequisites.
- X09-D: Only render success text matching actual acknowledged operation; forgetting cookie alone is not server deletion.
- X09-E: open X10 then Return/Escape restores this node’s values, draft, visible question and reading position.

### X10 · Explain or reassure without losing the guide.

**Phase / surface / wireframe:** preserve / assistant_overlay / W7/W8. **Prerequisite:** authenticated_guest_or_ephemeral.
**Required vocabulary:** contextual inline terms; no forced full lesson. Preflight and G1 apply.

**Exact proposed question:** Daylight · AI assistant
**Why asked / microcopy:** Ask about this question, the picture, or the comparison. You decide what changes.

| Answer / event | Visible proposed label | Confirmed next target |
|---|---|---|
| `question` | Send an explicit question | `X10` |
| `followup` | Choose a visible follow-up | `X10` |
| `propose` | Review a proposed profile update | `X01` |
| `return` | Return to your question | `@origin` |

**Reads:** flow.origin, knowledge, allowedContext, chat.draft. **Allowed writes:** chat.optionalHistory, chat.draft.
**Answer effects:** `question`: submit explicit chat with allowed minimum context only; `followup`: read reviewed response or allowed live request; `propose`: no profile write until X01; `return`: no profile/route change.
**Agent responsibility:** Use the current task and confirmed profile to explain why this matters. Direct answer first, sources and uncertainty, two relevant visible follow-ups, previous history explicit. No automatic textarea focus for a reading entry. Never commit an extracted fact or change the route without confirmation.
**Validation:** No background advancement, layout reflow, automatic profile writes, or unsolicited sensitive-context transfer. Focus contained; Escape/Return restores exact opener and scroll.
**Picture delta:** `none`; add only introduced concept(s), never change enrollment facts. **Progress:** preserve (preserve means unchanged phase). **Help:** X10 plus literal current task and permitted minimum context.
**Requirement IDs:** D25, D28, D33, D34, D35, D43, D44, D49, D54.

**Acceptance:**
- X10-A: each listed answer has exactly one defined next target after Continue.
- X10-B: Back, edit, help return, unknown and failed-save behavior obey G1; original text and prior confirmed entries survive.
- X10-C: only declared profile writes occur; picture changes obey concept prerequisites.
- X10-D: No background advancement, layout reflow, automatic profile writes, or unsolicited sensitive-context transfer. Focus contained; Escape/Return restores exact opener and scroll.
- X10-E: open X10 then Return/Escape restores this node’s values, draft, visible question and reading position.


## Clarifications bound to version 1.0

- The primary task free-text composer shows the AI-submission disclosure from first use; no durable write before A05 and no sensitive-list attachment without explicit task-specific permission.
- O09 presents Record my preference / Continue with checks open as unselected intent choices followed by one Continue; its `choose` and `continue` transitions are resolved after that action, not competing prominent buttons.
- The JSON concept dependency graph defines exact prerequisite queue order and cycle checking. Confirmed timingQuestion, not agent guesswork, sets the dateTask/partBDateTask aliases.

## D65 current presentation contract · October 21, 2026

Owner approved implementation in full. [Revision and before/after wireframes](UI_SIMPLIFICATION_REVISION.md), [completion evidence](UI_SIMPLIFICATION_COMPLETION.md) and `flow-contract.json` version `1.1.0-simplified` supersede historical separate-screen/lesson-queue presentation in this document. Keep legacy IDs for saved-guide migration.

| Current screen | Retained fields / behavior | Old IDs redirected |
|---|---|---|
| A02 | Recipient, optional caregiver wording in same submit | A02B → A02 |
| A03 | Medicare introduction plus voluntary depth question/free text | A04 → A03; old L00 → L01 topic navigation |
| O00 | Category and browse/personal mode; difference opens contextual routes topic | O01 → O00 |
| O03 | ZIP, inline county source/ambiguity, requested year | O04/O04B/O05 → O03 |
| C03 | Coverage components and review/change intention | C04 → C03 |
| J00 | Job status and requested task | J01 → J00 |
| J03 | Separate employment and coverage end dates; independent unknowns | J04 → J03 |
| L01/E01/E02/E03/E04 | Real topic choices with concise contextual teaching; useful Finish | L02–04 → E01; L05 → E02; L06–09 → E04; L10–11 → E03 |
| O11 | Relevant Medigap limitations and real next-task choices | L12–13 → O11 |

A05 saving is optional secondary/end action. No mandatory repeated definition pages. Unknown/skipped/reported/derived remain distinct; no new insurance rule or recommendation capability is introduced.

```text
SUN Daylight Medicare
1 Your goal  →  2 Your situation  →  3 Your options  →  4 Your next step
QUESTION + concise relevant teaching        CORE RELATIONSHIP MAP
explicit choices / related grouped fields   (only introduced architecture)
[Continue]  Back
☀ Ask Daylight · AI assistant
Your guide & privacy (secondary)

Ask overlay (over map; underlying geometry unchanged)
Ask Daylight  AI assistant                  Return
current task, answer/source, visible follow-ups
editable proposed reports + next task (answer mode only)
[Confirm and continue] (explicit, records reports)
composer / Send
AI may make mistakes. Privacy details
```

Acceptance: no preselection or automatic advance; every forced page asks a relevant question; back/edit preserves reports/drafts; old saved locations migrate; resume/save receipts and conflicts remain truthful; one phase marker per phase; no malformed empty pseudo-glyph; no consumer budget telemetry; $1 aggregate backend cap and plan gates unchanged. Desktop/tablet/phone and short-height overlay checks are required, with limits reported honestly.
