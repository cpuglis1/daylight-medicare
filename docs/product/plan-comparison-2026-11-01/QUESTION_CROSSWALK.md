# All 41 question meanings in the proposed comparison

November 1, 2026 · D87 design only · 38 primary meanings plus three aliases.

The source paths, requiredness, dependencies, source-layer review mapping and fourteen gap associations are retained in [question-decision-map.json](question-decision-map.json). Rule IDs refer to [DECISION_RULES.md](DECISION_RULES.md). These are conditional dependencies, not a mandatory sequence.

| ID | Existing meaning / comparison role | Rule | Use and unknown behavior |
|---|---|---|---|
| T01 | Requested task | R01, R16 | Clarify goal only if explicit intent is insufficient for the requested help. Education/browsing can continue; do not invent a goal. |
| T02 | Explanation depth only | R17, R16 | Ask optionally if familiarity would improve the explanation. No factual availability, candidate, fit or ranking gate. |
| T03 | Reported geographic scope | R02, R16 | Ask missing ZIP/county only for a geography-dependent requested check; reuse RC02. Geographic finding remains unscoped; no inferred county/residency. |
| T04 | Desired coverage start | R02, R04 | Ask desired timing only when it changes the requested check; soonest is a preference. No inferred month, effective date, eligibility anchor or deadline. |
| T05 | Current coverage categories | R03, R04 | Reuse current coverage reports; clarify consequential subtype/period only. Keep partial positives and missing baseline; no inferred A/B or absence. |
| T06 | Reported providers and list disposition | R06 | Ask only requested provider needs; reuse known names and distinguish explicit none from unknown. Unknown list is not no providers; listing a name is not a hard constraint. |
| T07 | Reported medicines and list disposition | R07, R08 | Ask medicines only for a requested care/coverage comparison; reuse existing items. Unknown list is not no medicines; partial items stay partial. |
| T08 | Routine care away need | R09 | Ask only if routine-away-care needs could change the requested comparison. Do not assume no travel, a location, or emergency evidence implies routine coverage. |
| T09 | Optional cost emphasis | R12 | Ask optionally if the person wants to express this tradeoff. No invented risk tolerance, numerical weights or cost model. |
| T10 | Optional priorities | R12, R15 | Reuse expressed priorities; ask optionally when it helps an actual tradeoff. No forced priorities, click-order weights or mandatory ranking. |
| RC01 | Beneficiary/helper scope | R01 | Clarify whose facts apply when consequential; reuse unambiguous first-person reports. No cross-person transfer or implied sharing authority. |
| RC02 | Permanent home and contextual locations | R02, R09 | Reuse T03; ask only missing permanent/moving/seasonal meaning relevant to the check. ZIP lookup is not proof of residency; preserve multiple places. |
| RC03 | Comparison year | R02, R14 | Confirm an explicit year only when absent/ambiguous for the requested evidence. No substituting 2026 research or unvalidated 2027 samples. |
| RC04 | Actual Medicare parts | R03, R04 | Ask actual A/B status for a finding needing it; never equate applied/getting started with active parts. Hold dependent entitlement/transition conclusion; learning remains available. |
| RC05 | Actual Part B start | R04, R05 | Ask only if an applicable timing/rights check requires the actual B month. No substitution for Part A chronology, birthday or requested start. |
| RC06 | Eligibility basis and age band | R04, R05 | Ask basis/age precision only for an applicable supported rule. No inferred birthday, exact eligibility anchor or personal premium. |
| RC07 | How current A/B benefits are received | R03, R05 | Reuse T05/RC04 where sufficient; clarify only actual delivery meaning needed now. No forced delivery category or inferred policy identity. |
| RC08 | Relevant change/event | R04 | Ask exact change/date only if the requested transition check needs it. Keep partial event/date; no inferred window. |
| RC09 | Current work source of coverage | R04 | Ask active-work versus retiree/other source only for relevant coordination/timing. Retired status is not retiree insurance; preserve whose employment applies. |
| RC10 | Basis-specific employer-size meaning | R04 | Use the actual applicable threshold variant only after basis/current-work context is known. Unknown/unbound threshold is not a payer-order determination. |
| RC11 | Separate job and health-coverage end | R04 | Collect only missing date/precision required by the relevant change check. Do not merge jobEnd and coverageEnd or invent exact days. |
| RC12 | Creditable notice and separate gap | R04, R07 | Ask the missing notice/period/gap meaning only when relevant; preserve independent known parts. Report of notice does not verify coverage; unknown gap cannot yield a penalty finding. |
| RC13 | Consequences for own group/retiree benefits and other people | R04 | At an actual relevant change, clarify only missing party/action/effect/period facts; reuse scoped administrator reports. Sole-insured status does not establish no impact on own benefits. No automatic consequence or collection of other people details. |
| RC14 | Reported HSA contributions | R04 | Ask only for a relevant supported contribution/transition check. A yes/no cannot decide chronology, retroactivity or tax consequences. |
| RC15 | Requested Medigap change/notice check | R05 | Ask exact relevant event/notice for the requested Medigap branch; reuse RC05/RC11. No generic underwriting/rights assertion from a branch choice. |
| RC16 | First Advantage and prior Medigap history | R05 | Use distinct first-plan/start/prior-policy reports only for relevant rights research. History is not verified return/issueability; gaps G01/G04 persist. |
| RC17 | Medigap replacement report | R05 | Ask only if replacement is part of the requested comparison/change. No inferred exemption, continuation, guaranteed issue or quote. |
| RC18 | Named assistance program reports | R10, R08, R11 | Reuse each named current/pending/unknown program; precision only for affected requested finding. Partial program knowledge is retained; no subsidy amount or qualification inference. |
| RC19 | Exact restricted-plan qualification context | R10 | Ask only exact relevant qualification report for a requested plan type. Unverified/unknown qualification is unresolved, not ineligible; no broad clinical intake. |
| RC20 | Each away-care place/need | R09 | Reuse T08/places; ask only missing location/type/period needed for routine access. Do not flatten multiple destinations or substitute emergency evidence. |
| RC21 | Each provider office/site | R06 | Resolve each requested provider site; present identity ambiguity rather than silently selecting a namesake. Internal ID/NPI match is not network or appointment verification. |
| RC22 | Each exact medicine product | R07, R08 | Resolve product/strength/form only as needed; brand preference remains optional. Strength is not quantity/dose; unknown preference does not erase known product facts. |
| RC23 | Each fill and exact pharmacy/channel | R08, R11 | Ask only missing per-item quantity/units/days supply/store/channel needed for a supported requested fill-price, quantity-limit or pharmacy-network finding; no full pricing prerequisite. No assumed fill, pharmacy choice or average-as-quote; coverage research may continue. |
| RC24 | Item-specific dispensing/administration context | R07, R08 | Ask the missing discriminator only when it changes an accepted coverage rule/research target. Clinic versus pharmacy alone cannot decide part, device, authorization or a separate problem. |
| RC25 | Optional budget and inclusions | R11, R12 | Ask optionally when the person wants a budget constraint; clarify what the amount includes. Unspecified scope cannot yield an all-in affordability/total-cost claim. |
| RC26 | Exact military/veterans coverage category | R03, R04, R10 | Ask only missing program subtype relevant to current baseline/coordination. Program category is not complete coordination evidence. |
| RC27 | Immediate coverage interruption concern | R04, R16 | Ask/reuse explicit interruption details only for supported continuity help. No invented completed help, coverage cancellation or eligibility finding. |
| RC28 | Targeted correction | R13, R16 | Apply clear targeted correction directly; ask only actual ambiguity in person/item/field/time. No newest-message-wins conflict resolution or acceptance ritual. |
| RC11.C1 | Alias for RC11 coverageEnd | R04 | Ask only missing coverageEnd; reuse a parent answer to the same field. No extra obligation and no substitution for jobEnd. |
| RC16.C1 | Alias for RC16 actual start | R05 | Ask only missing relevant actual Advantage episode start in the parent history context; keep first-entry status distinct. No extra obligation; requested future start cannot substitute. |
| RC16.C2 | Alias for RC16 priorMedigap | R05 | Ask only missing prior Medigap meaning in the parent context. No extra obligation or inferred right to return. |

All 78 baseline paths are covered by this map. The three aliases reuse their parent paths; the eleven clarification templates add wording, not readiness obligations. RC29/RC30 remain guards.

**Optional**: T02, T09, T10, RC25 and brand/generic preference within RC22. Unknown optional preferences do not block factual availability. The other questions become required only for a relevant requested finding and applicable branch. Unasked does not mean not applicable.

Every changed answer can invoke R13; every sourced claim must also satisfy R14/R18. R16 selects a useful next move from the existing meanings. The adapter extensions described in [PROFILE_MAPPING.md](PROFILE_MAPPING.md) preserve the baseline accounting and do not add mandatory questions.

Original wording and `source_dependencies` in the JSON preserve traceability. Later owner guidance and accepted finding-specific rules determine actual conditional use; they do not impose full pricing before RC24 or automatic year/assistance intake for RC25. RC13 includes relevant own-benefit consequences.
