# :8893 Plans backend correction · November 5, 2026

Owner requested usable supported plan details, precise material holds, independent publication/recommendation gates, and completion of the recommendation adapters. This supersedes the all-fields-held behavior of the first integration. Backend and data engineering remain the focus; the existing thin Plans UI is reused.

## Usable now

The explicitly enabled local research runtime serves the exact r13 dated reference through the same Plans APIs: **72 identities; 568 supported reference fields; 11 not-applicable fields; 141 material field holds; 200 fictional examples and 88 held examples**. Original r5/r12/r13 evidence and all 229 material holds are unchanged. A local reference is visibly distinguished from independent consumer publication approval. This is the owner's authorized local integration, not a fabricated reviewer acceptance or a public deployment.

The confirmed chat profile is read through its current owner/visit/input-bound receipt. No second profile, saved transcript, browser-authored fact, or automatic model call is introduced. The existing profile retains all 41 meanings. An explicit priority order produces a deterministic **published-term comparison**: 69 supported monthly premiums, 70 supported in-network medical limits, **68 plans with both**, four unranked for that combination. The four stay visible and are never assigned a bad score. Equal vectors remain explicit ties, including ties crossing third place. This is separate from a personal top three.

Contextual chat receives only the selected/compared reference fields and identity observations at deliberate Send, with exact review state and citations. Held amounts are suppressed. Reference context explicitly says independent consumer review is pending. View changes, profile changes, publication withdrawal and recommendation/finding revocation invalidate stale context. No live or paid conversational evaluation was performed.

## Independent boundaries

- `plans_publication.py` / `cms-slice/data-sources/plans-publication.json`: separate cell/example publication authority. `--local-research` enables the owner-authorized local reference. Ordinary/consumer mode still requires exact source-use and independent publication review. Publication does not depend on recommendation-method approval, personal checks or frontend hashes. Root revocation and exact-output withdrawal affect local and consumer modes. The original catalog's material holds cannot be overridden by any receipt.
- `plans_authority.py` / `plans-workspace-acceptance.json` v2: recommendation source/method/output receipts only. Source purpose, independent review, expiry, catalog and loaded/backend-code bindings remain enforced. The empty per-profile `cases` requirement was removed. No consumer/domain sign-off was invented.
- `plans_adapters.py`: reads typed r5 monthly-rate and in-network annual-limit decimals, validates units/currency/nonnegative finite values, resolves source locators, and intersects them with r13 field dispositions and current publication access. It never parses display strings. Hidden metric amounts and conditions are suppressed together.
- Profile checks are generated automatically. Explicit absence of doctors/medicines/routine away care removes the respective requirement; unknown, stale, conflicting or wrong-subject facts do not. Nonrestricted plans do not need an SNP/residence check. Special restrictions stay attached to the exact offering. Budget is conditional; no fixed-budget report is required of everyone. Broader priorities such as total cost/predictability remain unresolved when the two supported metrics cannot answer them. Current coverage, A/B enrollment reports and county identity are preparation, not verified personal findings.
- `VerificationFindings` reloads exact server-owned, profile-bound, plan/check-bound, dated findings. Each finding needs its own `personal_check` acceptance, exact scope, evidence references and unexpired review. Identity-only searches are rejected as coverage verification. Duplicate findings hold the affected check. No client write endpoint or new private-data persistence exists.
- The ranker consumes these adapters directly. It emits a personal top three only with accepted method/metrics and satisfied material checks. An unresolved candidate blocks only when its safe optimistic cost bound could affect the top three. Unknown values are never treated as expensive, zero-cost facts or poor fit. A known conflict stays visible and is excluded from the shortlist. No commercial features enter the pipeline.

## What still genuinely blocks personal recommendations

The live independent recommendation receipt remains pending, and there are no accepted personal verification findings. Existing provider/drug identity preparation is not proof of plan participation, drug coverage/cost or eligibility. Automated personal verification is **unavailable**, explicitly reported in the API; the completed adapter can consume exact reviewed findings without hand-authoring per-profile metric cases. It does not claim to have acquired those findings.

The exact independent **consumer publication** source-use/domain review remains pending separately. Existing 535-entry r4 internal-reference acceptance is preserved, not inherited by the new consumer purpose. Full historical L03 reconciliation is not imposed as a blanket prerequisite. No approval is being requested as a prerequisite to this already-authorized local implementation.

## API handoff for the separate UI

All existing requests remain same-origin, guest/CSRF protected, POST bodies only, and no-store:

- `/api/plans/catalog` `{}`: all 72, field/example dispositions, coverage counts, independent publication status and adapter capabilities.
- `/api/plans/workspace` `{token}`: current profile binding, per-plan checks, grouped work items and recommendation holds. No raw profile is copied into AI context.
- `/api/plans/priorities` `{token, order, confirmed:true}`: one or both `monthly_plan_premium`, `in_network_medical_limit`, in explicit order. Returns `reference_comparison` independently from `recommendation`.
- `/api/plans/detail` `{offeringId}`: projected terms, typed metrics, source lineage and fictional assumptions.
- `/api/status`: `plans_workspace` has scope, precise coverage and adapter status. Historical global `consumer_ready` is not used as a display switch.

Cells use `reference`, `published`, `not_applicable`, or `held`; `source_state` preserves the sealed disposition. `reference_comparison.first_three` is explicitly not personal recommendations; use `recommendation.top_three` only when its state is `supported`. `recommendation.plans[].checks` supplies precise per-plan states, report/evidence references and reasons. Keep all 72 inspectable. `plans-context-v1` remains view metadata only; the server rehydrates values. No plan price, preference, acceptance flag or arbitrary source text is accepted from the browser.

## Verification

See the adjacent machine-readable results and activation record. Tests exercise the real 72-plan source, preserved 229 holds, actual confirmed-profile adaptation, same-origin/owner/stale binding, typed metrics, independent publication, conditional requirements, reference ordering, and the entire recommendation path using **fictional** acceptance/verification receipts confined to temporary directories. That successful fixture is not a real approval. Source replays still reproduce all 200 numeric examples. Paid provider calls and outbound sockets are blocked by the test runner.

D64/D73 evidence: deterministic source/priority decisions exclude economics; all retained offerings remain visible; path/current-coverage and consequential conditions stay explicit; reported completeness is separate from external verification; no expanded saving or automatic AI transfer; no claim of all-market completeness, live availability, independent release or measured comprehension. Protected variants, frozen natural-state meanings, saved profiles and the shared budgets remain unchanged.

Activated and verified on the existing :8893 service at 20:13 UTC on November 5. Live API checks confirmed all counts above, the Humana H1036-217 $0 premium and $540/$720 fictional hospital examples, and the held H1032-241 premium with only `PREMIUM_BASIS_CONFLICT`. The affected regression suite passed 185 tests; final adapter recheck passed 33; frontend handoff tests passed 40. Desktop/tablet/phone views at 1440/834/390 pixels showed supported values with no horizontal overflow. The staged contextual prompt was verified without Send and then cleared. Only :8893 was restarted.
