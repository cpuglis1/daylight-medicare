# CMS pre-enrollment checklist check

November 11, 2026 · Deterministic check added in `alternatives/advisor-first/cms_checklist.py`.
Item names come from `infrastructure/daylight-operations` (CMS CY2026 agent/broker
guidelines; 42 CFR 422.2274(c)(12) and 423.2274(c)(12), as summarized in the
November 5 brokerage plan). The regulation text was not re-read for this check.
Whether software coverage meets the "agents and brokers discuss" standard is
still a counsel question.

## Update, later on November 11

The owner signed off the six draft statements. They now load from
`pilot-rules-r3-cms-checklist.json`, all twelve topics have reviewed content,
and the fixed "Before you enroll" step shows them and records the time. The
table below is the state the check found before that sign-off.

## Result

Daylight cannot hit all twelve items today. Six have complete reviewed teaching
content; six have none or are missing a point. A conversation cannot cover an
item it has no reviewed statement for, so no prompt change can close these.

| # | Item | Reviewed content today | Status |
|---|---|---|---|
| 1 | Plan type; doctors, pharmacy and hospitals in network | `advantage`, `routesintro`, `original`, `drugbasics`, `original_nationwide`, `checks` | Ready |
| 2 | Formulary coverage | `drugbasics` | Ready |
| 3 | Other needed benefits | `extras` | Ready |
| 4 | Premiums, including Part B | `costs`, `advantage`, `options` | Ready |
| 5 | Cost sharing | `costs` | Ready |
| 6 | Out-of-network rules | `original_nationwide` (one sentence) | Ready, thin |
| 7 | Coverage outside the U.S. | none | **Gap** |
| 8 | Effect on current coverage, including Medigap | Medigap and underwriting are covered (`switching`, `ma_trial_right`); nothing says current coverage ends when new coverage starts | **Gap (one point)** |
| 9 | Plan-year changes and the Evidence of Coverage | yearly change is covered (`annual_enrollment`); the Evidence of Coverage is never named | **Gap (one point)** |
| 10 | How to file complaints | none | **Gap** |
| 11 | Special Needs Plan requirements | none | **Gap** |
| 12 | Right to cancel | none (`ma_trial_right` is about Medigap rights, not cancelling an enrollment) | **Gap** |

## What now runs

- Every conversation turn returns `cmsChecklist`: for each item, whether the
  reviewed facts that cover it were actually delivered in this visit. It is
  counted from the delivered-teaching record, with no model call.
- "Review your info" shows "Before you enroll: N of 12 required topics covered
  so far" with each topic marked covered or not covered yet.
- A test pins the six gaps by name. It fails the day a reviewed fact closes one,
  so the list cannot drift silently.
- The receipt uses the same item names as the operations scorer, so it can be
  stored on a decision record when enrollment exists.

## What "always hit" still needs

1. Reviewed statements for the six gaps (drafts below).
2. An owner decision on where the guarantee sits. A conversation can be steered
   toward missing topics but cannot be relied on to reach all twelve. The
   dependable design is a fixed "Before you enroll" step that shows all twelve
   reviewed statements and records the time, with the conversation receipt as
   supporting evidence.
3. Counsel's answer on whether a shown-and-recorded step satisfies "discuss".

## Draft statements for the six gaps (not loaded, not reviewed)

These are drafts for your reviewer. None is in the product.

- **Coverage outside the U.S.** Original Medicare generally does not cover care
  outside the United States, with narrow exceptions. Some Medigap plans include
  foreign travel emergency coverage, and some Medicare Advantage plans cover
  emergency care abroad. Check the exact plan before relying on it.
- **Effect on current coverage.** Joining a Medicare Advantage or Part D plan
  ends your enrollment in the Medicare Advantage or Part D plan you have now.
  A Medigap policy cannot pay Medicare Advantage costs, and if you drop it you
  may not be able to get it back. Joining a plan can also end employer or
  retiree coverage for you and your dependents; ask the benefits administrator
  first.
- **Plan-year changes and the Evidence of Coverage.** A plan's benefits,
  premiums, cost sharing, drug list and network can change each January 1. The
  Evidence of Coverage is the plan's full statement of benefits and rules, and
  the Annual Notice of Change each fall lists what will change.
- **Complaints.** You can file a complaint, also called a grievance, with the
  plan. You can also call 1-800-MEDICARE or file a complaint at Medicare.gov.
- **Special Needs Plans.** Special Needs Plans are Medicare Advantage plans for
  people in specific situations: having both Medicare and Medicaid, having
  certain chronic conditions, or living in an institution or needing that level
  of care. The plan has to confirm that you qualify.
- **Right to cancel.** You can cancel an enrollment request before the coverage
  starts by contacting the plan. After coverage starts, leaving or switching is
  limited to Medicare's enrollment periods.
