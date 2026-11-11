# Pilot security: decisions for Chris

November 7, 2026. D99 approves the $100 total budget and participant usage tracking.
D100 approves private GitHub Free with manual founder review for the pilot.
D101 approves the proposed scope and numeric retention and selects AWS
`us-east-1` with the OpenAI GPT API for the pilot.
D98 authorizes stage-1 drafting and developer protections. This packet addresses SA-27, SA-02,
SPEC-D3/D4/D5 and preparation for SA-01/SA-06/SA-17; it preserves D64/D73,
the existing D86/D90 local budgets, source STOPs and release/acceptance gates.

## 1. Approved bounded invite-only scope

**Approved:** up to 20 individually invited adults within the existing Collier
first-time-enrollee scope, ending December 23, 2026. Start with guest visits
only, using accepted 2026 sample capabilities. Keep saved profiles, public
signup, enrollment, SMS, paid data calls, family/partner access and automatic
invitation propagation disabled. Use founder-only administration. Personal
recommendations remain subject to their separate gates.

The [accepted spec amendment](../../company/LAUNCH_SECURITY_SPEC_2026-11-06.md#81-proposed-invite-only-gate-1-amendment--november-7-2026)
names the specific deferrals: managed bot/edge automation controls, behavior
scoring, statistical cap calibration, and independent GitHub review count while
there is only one maintainer. Each has a deadline before public access. Core
privacy, vendor, authorization, web and spending protections remain mandatory.

**Tradeoff:** fewer systems to build for a small observed trial, with more
founder oversight. Reused/leaked invitations, unexplained spend or broken access
isolation pause admissions. A private pilot is not a release or privacy waiver.

Decision: **Approved November 8, 2026 (D101).** Review the deployed pilot before
admitting participants.

## 2. Approved: one $100 total pilot model budget

**D99 owner decision:** “lets just have a 100 dollar limit on the pilot and we
track how much each user goes through.” This replaces the earlier layered
SPEC-D3/D4 budget proposal. The amount is an allowance, not a cost forecast.

| Control | Setting / behavior |
| --- | --- |
| Whole-pilot limit | **$100 cumulative model spend**, shared across all participants and all pilot sessions, without a calendar-month reset. |
| Individual usage | Track each participant's cumulative dollars, tokens and sessions using an opaque participant/invitation reference. Reporting only: no personal dollar cap. Returning sessions retain the same participant attribution. |
| Sublimits | None per hour, day, session, invitation or guest/saved pool. Remove the $90/$10 split and fixed reserve bucket. Guest/saved labels may classify usage but do not allocate money. |
| Included charges | Every pilot model stage, classifier, summarizer, retry and unresolved/in-flight charge. Failed or abandoned sessions still count. Shared/unattributable charges count against the total and appear separately in reports. |
| Stop behavior | Admit paid work only when its conservative reservation fits within the remaining $100. Settle actual usage and release only known-unused reservations. Stop new paid calls when no room remains or accounting integrity fails. |

Reservations are temporary accounting for calls already in progress, **not an
extra quota or a withheld $10 allowance**. They prevent concurrent requests from
each spending the same remaining dollars. Keep bounded output/retries and
idempotent settlement; do not treat missing usage or ambiguous network failures
as free. Preserve progress and explain when chat is paused. A new session,
invitation replacement or calendar rollover must not replenish the pilot total.
Because there is no personal quota, one participant could consume much of the
shared allowance; the per-participant report makes that visible.

The next implementation must reconcile against provider usage, retain tested
kill switches and use any verified provider limit as a backup. A provider's
monthly limit alone does not enforce a whole-pilot limit spanning months.
Optional alerts at $50/$80/$100 are notifications, not additional ceilings.
The current best-effort traces do not yet enforce this budget.

This decision concerns model/API usage in the prior budget proposal. Hosting,
database, storage, email and GitHub bills require separate cost control; this
does not authorize purchases. Checkout/enrollment and other paid actions remain
outside the proposed pilot scope. Existing local development allowances remain
unchanged; no agent-run paid/live conversation test is authorized.

**Status: budget direction and per-participant tracking approved November 7,
2026 (D99). Runtime enforcement is not installed.** Detailed logging fields and
retention remain decision 3; pilot traffic still requires accepted launch gates.

## 3. Approved numeric usage extension and retention

**D99 approves tracking each participant's usage. Recommend SPEC-D5 details:**
add a versioned, fixed-schema usage record with strict
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

Decision: **Approved November 8, 2026 (D101).** Raw chat remains visit-only.

## 4. Approved for the pilot: private GitHub Free with manual review

**Observed November 7:** the repository is private, and the actual `main`
protection API returns HTTP 403: “Upgrade to GitHub Pro or make this repository
public to enable this feature.” Repository security-analysis metadata is absent;
native secret scanning/push protection cannot be claimed verified. Existing local
and CI checks work independently of that feature.

**D100 decision:** keep the repository private on Free with the pilot procedure below.
Pro is not needed to finish the engineering work or run the checks. It adds
server enforcement of protected branches/required reviews for this private
personal repository. [GitHub plan comparison](https://docs.github.com/en/get-started/learning-about-github/githubs-plans),
[protection availability](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches).

| Free control | Actual status / next action |
| --- | --- |
| Local secret/publication checks | Hook active in this checkout; its older index still requires deliberate policy-file reconciliation. Install in each clean development checkout. Local hooks are bypassable. |
| Automated tests and dependency scanning | Both checks passed on PR head `1a1a348`. The founder reported the merge, and GitHub verified merge commit `ebced4e` on private `main`. Check the final commit's results before every merge. |
| Dependabot alerts and update proposals | Alerts/security updates verified enabled; expanded Python update configuration is in PR #4. Review updates; no automatic merging. |
| PR-only work and founder review | Use branches, inspect the diff/outgoing history, record founder review and passing check links for the exact commit. No direct main pushes or force-pushes under the procedure; GitHub Free cannot enforce this private-branch rule. |
| Small access surface | Retain founder-only write access and passkeys/recovery; review authorized apps/tokens and grant only needed scope. Personal authentication and permissions still need verification. |
| Release control | Proposed next stage: founder approves an exact tested revision for deployment; no automatic production deploy on a main-branch change, and no production credentials in routine PR CI. Not installed by this packet. |
| CI cost control | Use included Actions compute/storage, inspect account billing budgets and block paid overage where supported. Existing billing settings were not changed or verified. Retain release evidence before artifacts expire. |

Dependabot and dependency inventories are available without a paid security
product. Our local/CI scanners do not imply GitHub-native private secret push
protection, and Pro alone does not supply that product.
[Security feature availability](https://docs.github.com/en/code-security/getting-started/github-security-features).
Private-repository Actions have included usage and separate storage allowances;
they are not unlimited. If a payment method is present, verify spending budgets
before relying on a no-overage assumption.
[Actions billing](https://docs.github.com/en/billing/concepts/product-billing/github-actions).

**Residual gap:** a credential with write permission can bypass the procedure
and push/merge failing or unreviewed code. More CI, CODEOWNERS or local hooks
cannot replace server-side rejection. D100 accepts this residual gap for the
invite-only pilot. The approved procedure is a launch requirement under D100.
Before public access, implement enforced PR/check/review requirements and a
second qualified reviewer. Revisit earlier if write access or automated
deployment expands. No purchase, visibility or settings change was made.

@cpuglis1 is the sole assigned maintainer. Record founder review and passing check
links against the final commit before each merge. Independent review resumes with
a named second reviewer before public access. PR #4 merged on November 7, 2026.

## Your account-security actions (SA-01 preparation)

**D101 selects AWS `us-east-1` and the OpenAI GPT API.** The founder reports
security setup and signed agreements. The immediate dependency is temporary
deployment access to the intended AWS account. Follow the
[deployment handoff](../../../audit-evidence/pilot-deployment-20261108/README.md).

1. **GitHub.** Confirm a founder passkey or hardware key and independent
   recovery method. Check Actions metered spending in personal billing. Enable
   included-usage alerts and a hard stop for paid overage if you want Free to
   be the ceiling. [Passkeys](https://docs.github.com/en/authentication/authenticating-with-a-passkey/managing-your-passkeys) · [Budgets](https://docs.github.com/en/billing/how-tos/set-up-budgets)
2. **AWS.** Connect a temporary IAM Identity Center session scoped to the
   pilot deployment. Record which AWS Artifact agreement covers the account.
   [AWS CLI SSO](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-sso.html) · [AWS Artifact](https://docs.aws.amazon.com/artifact/latest/ug/managing-agreements.html)
3. **OpenAI API.** Verify the dedicated project's BAA scope, eligible model
   and endpoints, effective retention and processing location. Put its scoped
   key directly in the approved AWS secret store when binding the live route.
   [OpenAI API BAA](https://help.openai.com/en/articles/8660679-getting-a-business-associate-agreement-for-the-openai-api) · [API data controls](https://developers.openai.com/api/docs/guides/your-data)
4. **Daylight.** Sign the [HP-01 security and privacy official designation](../../company/security-program/HP-01_SECURITY_PRIVACY_OFFICIAL_2026-11-07.md).
   Confirm founder-only administration, monthly access review and same-day
   removal on departure. Share only non-secret confirmations and record
   references. Keep keys and recovery codes in their designated stores.

After the decisions and account setup, engineering can wire the approved
runtime identity and model route, check pricing and billing reconciliation,
validate the real TLS origin, log redaction and admission controls, and exercise
kill switches with fictional traffic. The founder then reviews the exact
deployment and decides on participant admission. SA-17 pilot cost evidence
starts when the founder can observe real supported completions.

## Approval record

| Decision | Status | Owner/date |
| --- | --- | --- |
| Pilot scope and exact exception list | Approved | Chris / 2026-11-08 / D101 |
| SPEC-D3/D4: one $100 whole-pilot model limit; no dollar sublimits | Approved direction; runtime pending | Chris / 2026-11-07 / D99 |
| Track cumulative usage per participant | Approved direction; instrumentation pending | Chris / 2026-11-07 / D99 |
| SPEC-D5 numeric usage fields and retention | Approved | Chris / 2026-11-08 / D101 |
| Private GitHub Free and temporary manual enforcement/reviewer procedure | Approved for invite-only pilot | Chris / 2026-11-07 / D100 |
| PR #4 merge | Verified on private `main` at `ebced4e` | Founder reported merge / 2026-11-07 |
| Host, region and provider | AWS `us-east-1` with OpenAI GPT API. Exact account and route verification pending. | Chris / 2026-11-08 / D101 |
| AWS hosting budget | $20/month alert budget, owner-reported. Verify its account scope before provisioning. | Chris / 2026-11-08 / D102 |

The D99–D101 decisions are recorded in owner requirements, directive history
and current state. Participant admission remains subject to deployed review.
