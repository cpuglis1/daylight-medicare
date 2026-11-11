# Collier validation — owner review required

Prepared October 20, 2026. This is the owner queue for the [current plan](COLLIER_DATA_GAP_PLAN_current.md), tracked by C44. It separates decisions and attestations Codex cannot supply from source checks Codex can still perform.

**Nothing in this file is validated, waived or approved by being moved here.** Required unresolved items still block consumer release. Legal approval under C12 is already complete and is not being reopened. C01 remains deferred; all existing holds remain in force.

## 1. Cannot be completed by Codex acting alone

| ID | Item requiring your review | Why outside participation is necessary | What you need to provide or arrange |
| --- | --- | --- | --- |
| O01 | **Independent Medicare subject-matter acceptance** — C36 / DQ-012 | Codex can prepare and check the evidence, but cannot supply an independent human review of its own work or attest to another person's approval. | Assign a named qualified Medicare reviewer. The reviewer must review the exact fields, interpretations, source evidence, cases and immutable release; record their name, scope, date, decision and refresh deadlines. Missing evidence must be resolved before acceptance. |
| O02 | **Source access and authority** — C11, C17/C18/C20/C22, parts of C38/C40/C41 | Codex cannot grant CMS/insurer credentials, approve source reuse on a supplier's behalf, license a feed, or remove an origin's access restriction. Technical access and permission are separate. | Obtain documented access/permission from the relevant source owner, or provide an authorized export. An access grant alone does not validate its data. The Medicare.gov STOP stays active until a documented resolution is reviewed. |
| O03 | **Official eligibility, enrollment, underwriting and binding quote decisions, if later in scope** | Source rules and synthetic examples cannot establish an individual's actual eligibility, policy issuance, underwriting outcome or binding premium. Those decisions belong to the administering agency, program or insurer. | Use the responsible organization for the actual determination or quote. This is a boundary for future personal use, not a request to collect personal data or reopen H01/H02/H09. R1 can explain verified rules and referrals without asserting a personal determination. |
| O04 | **Participation confirmation when published evidence cannot resolve an exact case** — C26–C28/C42 | Codex can research exact providers, locations, plans and networks. It cannot speak for the insurer/provider, certify an undocumented contract, or guarantee future participation, appointment availability or claim payment. | If public evidence remains insufficient or contradictory, obtain dated insurer/provider confirmation identifying the exact facility/clinician, location, medical network, plan and year. New outreach requires an explicit instruction; none has been sent. This does not transfer all 118 pending hospital cells to you. |
| O05 | **Actual future drug costs, claims and payment outcomes** — C20/C40; H01 held | A reproducible estimate can be validated against an adequate authorized source. It cannot certify what a future claim will pay, what a pharmacy will charge at dispensing, or future changes in coverage, assistance or treatment. | Keep validated estimates explicitly conditional. Obtain an actual quote/claim determination from the responsible plan/pharmacy when an actual transaction is needed. Do not treat a synthetic worked case as a guaranteed bill or reopen the personal calculator. |

## 2. Blocked by missing outside evidence — Codex can validate after it arrives

These are not permanently beyond validation. The missing input or source-owner action is outside Codex's control; extraction, matching and reconciliation remain Codex work.

| ID | Missing input | Last recorded evidence | Owner action / condition for resuming |
| --- | --- | --- | --- |
| E01 | **Authorized current Medicare.gov observations or an adequate authorized replacement** — C17/C18/C20/C22/C38 | Public bootstrap returned HTTP 403 on October 20. Collector STOP is active. Current all-70/four-ZIP observations, fixed drug-price scenarios and Medigap search universe were not captured. | Resolve access through CMS/source owner or provide an authorized capture/export with exact inputs, year, geography and timestamps. Codex can then validate schema, replay queries and reconcile both directions. No alternate-browser/proxy retry is an owner-review shortcut. |
| E02 | **Responsive Florida OIR records and rate evidence** — C23/C24/C41, DQ-011 | Case **26-045612** has an acknowledgment. The last saved inbox check, October 20 at 17:15 UTC, found no responsive dataset. Captured CHOICES amounts have unverified effective dates and no filing-rate reproduction. | Supply or arrange delivery of the responsive records and accessible filing/rate tables. Review any fee request before spending; no fee is authorized. Codex can then join insurer/NAIC/form/variant/date/rating assumptions and reproduce rates. |
| E03 | **Adequate authorized 2027 drug-pricing evidence** — C11/C20/C40, DQ-007/008 | The source assessment found no adequate per-drug price source in the captured monthly 2027 or quarterly 2026 files. The last saved inbox check found no CMS reply. Commercial leads are unlicensed/unvalidated; H01 remains held. | Obtain the CMS response, an authorized source/export or a supplier proposal with data definitions, effective dates and permitted use. Any purchase/licensing decision is yours. Codex can assess adequacy and run synthetic worked-cost checks after access is established. |
| E04 | **Definitive source clarification if research cannot resolve a material ambiguity** — C39/C40, DQ-003/004 | H1889-026 and H5594-017 retain $7.30/$0 premium-basis differences. Selected Trulicity quantity units are unresolved. Two Optimum carrier formularies are one version ahead of pinned CMS. | No immediate handoff: Codex should first finish available official-document research and version reconciliation. If still unresolved, obtain written CMS/carrier/PBM clarification of the exact field, population, unit, version and effective period. Codex can check that clarification against the captured rows. |

## 3. Work staying with Codex

These items remain unfinished work in the main plan; they are **not** being classified as impossible or delegated to you:

- Finish exact-plan 2027 SB/EOC checks across all 70 records: every required/displayed field, unit, period, exception, network condition and eligibility qualification.
- Continue public carrier availability checks and explain restricted enrollment and conflicting service-area evidence.
- Resolve premium and quantity interpretations from available primary documents; compare full affected formulary versions and expand drug/restriction checks.
- Continue independent public pharmacy and provider/location/network research. Endpoint reachability, NPI identity and broad payer lists remain insufficient by themselves.
- Validate OIR records, filings and rate calculations once supplied; preserve illustrative status where appropriate and distinguish it from acceptance.
- Maintain evidence hashes, reconciliation reports, tests, refresh checks, release binding and suppression of unaccepted outputs; prepare the reviewer packet and record genuine review decisions.

## Review order and completion evidence

1. Assign the reviewer for O01 while source work continues. The [prepared packet](cms-slice/reports/collier-gap-20261020/validation/REVIEW_PACKET.md) and [unsigned reviewer template](cms-slice/reports/collier-gap-20261020/validation/reviewer-template.json) are available.
2. Review E01–E03 for source access and delivery. Keep O02 permissions and actual data availability explicit; neither substitutes for the other.
3. Escalate E04/O04 only where further public-source research cannot settle the exact claim. Keep the disputed output unavailable meanwhile.

To close an item, retain the responsible person's/organization's identity, exact scope, dated source or decision, source hash or durable receipt, effective period and applicable review deadline. Codex then checks the evidence and updates the linked checklist item. Owner review alone does not convert unknown values into accepted facts.

The packet currently binds candidate `naples-98038a43549f438d8c38`; all 2,036 required claims remain pending in that packet. Its retained source-review deadline is **2026-10-21 at 01:33 UTC**. This file does not extend it, change the acceptance registry or enable consumer access. A changed or expired candidate needs refreshed evidence and a new bound review.

Supporting records: [validation status](cms-slice/reports/collier-gap-20261020/validation/validation-status.json), [mail check](cms-slice/reports/collier-gap-20261020/validation/mail-status.json), [source-access log](cms-slice/reports/collier-gap-20261020/validation/source-access-log.json), [OIR acknowledgment](cms-slice/reports/collier-gap-20261020/c16-c23/c23-oir-acknowledgment.json), and [acceptance standard](docs/DATA_VALIDATION_ACCEPTANCE.md).
