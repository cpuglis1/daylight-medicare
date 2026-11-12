# Daylight tiered sorting · method v1 (D147)

`daylight-tiered-v1-20261112` · November 12, 2026 · **evaluation only**

The owner directed a rudimentary deterministic recommendation for fictional
evaluation: “a tiered filtering scoring system, that prioritizes the preferences
dynamically … run that for all MA, Medigap, Part D,” with three groups (“priority
group”, “filtered, but not stated priority”, “not-filtered to”), no Part D pick
while medicines are unchecked, and the reasons shown on each plan “with little
checkmarks.”

It runs only on the unified local demo (:8895). The pilot gate cannot run with
the local demo, so pilot participants never receive its inputs or results. It is
not a consumer recommendation release; D143's counsel answer is still required
before real recommendations. No model call, no profile write, nothing saved.

Code: `alternatives/advisor-first/recommendation_engine.py` (method),
`recommendation_http.py` (`POST /api/recommendation`, local demo only),
`web-8894/recommendation-view.js` (display; computes nothing).

## Inputs

Only details the person reported in the conversation (status `reported` or
`derived`; “unknown” and “check later” count as not stated). Nothing is inferred.

| Input | Source |
| --- | --- |
| ZIP, county, plan year | Part D/Medigap profile inputs |
| Medigap pricing details and reported age | Medigap profile (a 64-year-old is priced at 65; eligibility uses the reported age) |
| Doctors | `needs.providersStatus` = `list` |
| Medicines | `needs.medicinesStatus` (`yes` / `no` / `unknown`) |
| Travel | `needs.travel` (`elsewhere_us`, `outside_us`) |
| Cost preference | `needs.costPreference` (`lower_monthly`, `predictable`) |
| Stated priorities | `needs.priorities` (`doctors`, `drugs`, `bills`, `travel`, `total_cost`) |
| Current coverage | `coverage.current` (employer, retiree, military, Medicaid …) |
| Medicaid | `coverage.current` or the RC18 answer |

Inputs naming commission, payout, compensation, referral fees, lifetime value
or revenue are rejected. Plan commercial fields are never read.

## Tiers

1. **Who can join.** A plan whose joining rule fails, or is not confirmed, is set
   aside (“Doesn’t meet your needs, or you may not qualify”) and never suggested.
2. **What you need.** A failed need sets the plan aside. v1 has one need: a
   Medicare Advantage plan without drug coverage, unless the person reported
   military or retiree drug coverage (most Advantage members cannot add a
   separate drug plan, and going without can bring a Part D late penalty).
3. **Stated priorities.** A plan that fails any stated priority moves to
   “Meets your needs, not all your priorities.” Otherwise it is in “Matches your
   priorities” (or “Meets your needs” when no priority was stated).
4. **Inside a group:** more stated priorities met first, then more other
   preferences met, then the tab's cost order.

A check is ✓ met, ✗ not met or ? not checked. **Not checked never counts
against a plan** in tiers 3–4. Ties share a rank. A plan missing an amount the
order needs stays in its group, unranked, listed after the ranked plans; it is
not treated as worse and is never suggested.

The suggested plans are the rank-1 plans of the first group, unless a no-pick
rule applies.

## Checks by tab

| Preference | Medicare Advantage | Medigap | Part D |
| --- | --- | --- | --- |
| Keep your doctors | ? network not checked | ✓ any doctor who takes Medicare; ? if Medicare SELECT | — |
| Your medicines | ? drug list not checked | — (drugs are separate) | ? drug list not checked |
| Care in other states | ✓ PPO · ? HMO-POS · ✗ HMO | ✓ | — |
| Care outside the U.S. | ? not in the plan information | ✓ C, D, F, HDF, G, HDG, M, N · ✗ others | — |
| Predictable costs | (orders the tab) | ✓ C, D, F, G · ✗ others, with the reason | (orders the tab) |
| Total yearly cost | ? needs medicines and care use | ? | ? |

Eligibility: Advantage D-SNPs need reported Medicaid (✓ / ✗ / ? when not
reported); other special-needs and Erickson rules are ? and therefore set aside.
Medigap Plans C, F and HDF need Medicare eligibility before 2020, read from the
reported age: 72+ ✓, 70 or younger ✗, 71 ?.

Cost order inside a tab: Advantage by monthly premium then in-network yearly
limit (limit first when the person wants predictable costs); Medigap by listed
monthly premium; Part D by standard monthly premium then deductible (deductible
first for predictable costs).

## No pick

- **Part D and Medicare Advantage:** no pick unless the person reported no
  medicines, because drug lists are not checked yet. Plans are still grouped
  and ordered.
- **Coverage path** (Original Medicare with Medigap and Part D vs. Medicare
  Advantage): compares the stated preferences on both sides (doctors, travel,
  predictable costs, and lower monthly cost from the lowest listed Medigap plus
  drug plan premium vs. the lowest Advantage premium among plans not set aside).
  No pick when nothing is stated, when both sides tie, or when the person
  reported coverage through a current job (timing comes first).
- Medigap underwriting outside the open-enrollment period is always noted.

## Known limits (v1)

Doctors, networks and drug lists are not checked; personal drug costs and total
yearly cost are not computed; Advantage foreign-travel benefits, star ratings,
Part B givebacks and extra benefits are not read; the C/F rule is an age proxy;
enrollment periods and plan availability are not checked. Each limit appears as
? on the plan rather than as a guess.
