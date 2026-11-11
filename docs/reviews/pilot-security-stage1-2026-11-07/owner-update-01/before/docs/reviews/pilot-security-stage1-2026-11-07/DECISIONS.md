# Pilot security: decisions for Chris

November 7, 2026. **Recommendations awaiting approval.** D98 authorizes stage-1
drafting and developer protections only. This packet addresses SA-27, SA-02,
SPEC-D3/D4/D5 and preparation for SA-01/SA-06/SA-17; it preserves D64/D73,
the existing D86/D90 local budgets, source STOPs and release/acceptance gates.

## 1. Approve a bounded invite-only scope

**Recommend:** up to 20 individually invited adults within the existing Collier
first-time-enrollee scope, ending December 23, 2026. No public signup, enrollment,
SMS, paid data calls, family/partner access or automatic invitation propagation.
Founder-only administration. Use only separately accepted capabilities; this
does not authorize personal recommendations while their gates remain held.

The [proposed spec amendment](../../company/LAUNCH_SECURITY_SPEC_2026-11-06.md#81-proposed-invite-only-gate-1-amendment--november-7-2026)
names the specific deferrals: managed bot/edge automation controls, behavior
scoring, statistical cap calibration, and independent GitHub review count while
there is only one maintainer. Each has a deadline before public access. Core
privacy, vendor, authorization, web and spending protections remain mandatory.

**Tradeoff:** fewer systems to build for a small observed trial, with more
founder oversight. Reused/leaked invitations, unexplained spend or broken access
isolation pause admissions. A private pilot is not a release or privacy waiver.

Decision: **Approve / amend / reject this exact scope and exception list.**

## 2. Approve a $100 model-spend envelope, not a cloud purchase

These are deliberately small operating limits, **not measured cost forecasts**.
Twenty people × an illustrative $1 journey × three attempts = $60, leaving
contingency. The $1 assumption is unmeasured; do not claim it predicts completion
or authorizes paid testing. The controls need metering and reconciliation before
activation. A fixed provisional cap is the proposed SPEC-D4 alternative to the
spec's unmeasured 20× persona-runner estimate.

| Control | Proposed setting | Meaning |
| --- | --- | --- |
| Provider organization ceiling | $100 per UTC calendar month | Backstop for pilot model calls only; retain a separate fictional-development organization/account and keys. |
| Application pilot ceiling | $90 across the entire pilot, without a month-boundary reset | Includes every classifier, summarizer, main call, retry and uncertain charge. Leaves $10 below the provider ceiling for reconciliation/in-flight differences. That $10 is not a discretionary extra allowance. |
| Guest/no-saved-profile pool | $60 for the pilot; provider workspace limit $65/month | Invited guests still need an invitation; “anonymous” means no saved identity, not public access. |
| Saved-profile pool | $30 for the pilot; provider workspace limit $35/month | Available only after saving permission and SA-12 pass. If saving stays disabled, this pool stays unavailable; a transfer needs a recorded budget configuration decision. |
| Checkout/enrollment pool | $0; server-disabled | No checkout, SMS, enrollment or paid third-party API usage in this scope. |
| Burst ceiling | $10 across all pilot model calls per rolling hour | An additional shared admission limit; not $10 per participant. |
| Daily ceiling | $25 across all pilot model calls per UTC day | Stop admitting new paid work at the limit. |
| Per-session allowance | $5 | Provisional safety allowance, not an observed p99 or a forecast. |
| Per-invitation allowance | $10 across sessions | A new window/session cannot reset a participant's cumulative allowance. A returning saved profile retains its original invitation/pool accounting. |
| Spend alerts | 50%, 80%, 100% of each configured ceiling | For the $90 usable cohort budget: $45 / $72 / $90. Also alert on provider/cloud thresholds. Alerts do not stop charges. |

All applicable limits must have room for a conservative reservation **before**
each paid request, including bounded output and permitted recovery. Reserve and
settle atomically across session, invitation, pool and total budgets. Do not
interrupt an already admitted response just because an app threshold is reached;
the provider may still reject a call at its own cap. Keep tools/progress usable
with an honest chat-paused message. Existing and saved sessions may continue
within their reserved/separate funds; no group is promised service beyond the
global ceiling. Founder review can increase a person's allowance within the
unchanged cohort total; any increase to total spending is a new decision.

A missing ledger, unknown price, missing usage or ambiguous network failure
cannot become a zero-cost call. Keep its conservative reservation until
reconciled; if accounting integrity is unavailable, stop new paid admissions.
The current best-effort tracing wrapper is not this enforcement ledger.
No automatic failover to another provider or paid service is authorized.

**Separate cloud budget:** model limits do not cap hosting, database, storage,
email, GitHub Actions or other cloud bills. Prepare cloud alerts at 50/80/100%
of a **proposed $100/month planning threshold**, with an owner escalation before
provisioning; this is neither a hosting quote nor a hard cloud cap. Exact hosting
costs, region, contracts and provisioning still need their own reviewed plan.
The existing $5/provider/UTC-day local development allowances remain unchanged;
this proposal does not authorize any agent-run paid/live conversation test.

**Provider feasibility:** the current Anthropic documentation supports separate
workspace limits under an organization limit. Its Build tier's $1,000 monthly
cap is above this proposal; no tier upgrade is justified for this pilot. Actual
account/contract eligibility and supported features still require verification.
[Official limits](https://platform.claude.com/docs/en/api/rate-limits), checked
November 7, 2026. Billing alerts can lag and cannot substitute for admissions
controls and the three tested kill switches in spec §3.7.

Decision: **Approve / amend / reject SPEC-D3 and SPEC-D4 above.** Approval records
the future configuration; it does not claim that the controls are installed or
permit pilot traffic before Gate 1 evidence is accepted.

## 3. Approve only the numeric usage extension

**Recommend SPEC-D5:** add a versioned, fixed-schema usage record with strict
types and retention, detailed in [LOGGING_PROPOSAL.md](LOGGING_PROPOSAL.md).
Existing trace fields already include tokens/model/stage/latency; reuse those
instead of adding arbitrary metadata. New fields supply dollar accounting,
pool/session linkage, counters and a small fixed outcome list.

Retain detailed usage records for 90 days from creation, then delete them through
an authorized expiry process. Keep only non-identifying cohort totals for 12
months. No chat text, prompt/response, health facts, names/contact details,
raw IP/device fingerprint, arbitrary URL/error text or commercial economics.
Founder-only inspection; no user-level telemetry sent to coding agents or
external analytics. Any report brought into development must be aggregate or
fictional.

**Separate open transcript question:** the November 7 draft
[HP-02 §6](../../company/security-program/HP-02_DATA_CLASSIFICATION_POLICY_2026-11-07.md)
records an intended pilot transcript study and says its conditions need
confirmation and a numbered decision before building. This numeric proposal
does not resolve or implement that separate change. The current no-new-raw-chat
persistence rule remains operative for this work. A transcript study needs its
own consent, approved storage/access, expiry and governance decision.

Decision: **Approve / amend / reject this numeric field and retention contract.**

## 4. Keep GitHub private and resolve enforcement/review

**Observed November 7:** the repository is private, and the actual `main`
protection API returns HTTP 403: “Upgrade to GitHub Pro or make this repository
public to enable this feature.” Repository security-analysis metadata is absent;
native secret scanning/push protection cannot be claimed verified. Existing local
and CI checks work independently of that feature.

**Recommend:** keep the repository private and approve GitHub Pro for this
personal-account repository, at the price shown in your billing checkout. Do
not change visibility to get free controls. Then enforce PRs, up-to-date
`repository-checks` and `dependency-security`, resolved conversations, no
force-pushes/deletion, and application to administrators. No purchase or settings
change has been made by this packet. [Official protection availability](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches).

**Review is a separate decision:** @cpuglis1 is the sole assigned maintainer.
Recommend the temporary founder review procedure in decision 1 for agent-authored
pilot changes, followed by a named second reviewer before public access. Until
that person is assigned, use zero independent GitHub approvals and report the
exception; never label author self-review independent. If you do not accept this
temporary procedure, assign a second reviewer before pilot code is accepted.

Decision: **Approve private + Pro; accept the temporary founder review procedure
or name a second reviewer now.** I can prepare/apply the exact protection once
the plan permits it. The purchase and personal authentication are your actions.

## Your account-security actions (SA-01 preparation)

Register a passkey or hardware key for each production administration account;
keep a second recovery method under your control. Use named accounts, no shared
logins. Confirm founder-only access and a monthly access review, with same-day
removal for anyone who leaves. Do not put recovery codes or API keys in this
packet or chat. I can prepare service roles and access-audit code in the next
stage; no cloud roles, customer access or production log storage were changed.

## Approval record

| Decision | Status | Owner/date |
| --- | --- | --- |
| Pilot scope and exact exception list | Pending | — |
| SPEC-D3/D4 budgets and fixed provisional safety cap | Pending | — |
| SPEC-D5 numeric fields and retention | Pending | — |
| Private GitHub plan and reviewer procedure | Pending | — |

Approval must be recorded against this version in the owner requirements,
directive history and current-state document. No checkbox is pre-approved.
