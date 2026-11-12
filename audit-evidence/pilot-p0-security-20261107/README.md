# Pilot P0 security and abuse

November 7, 2026. D99 and D100 govern this work. Daylight now has a loopback
rehearsal for the invite-only pilot. Production Gate 1 remains open.

| Item | Evidence in hand | Needed to close |
| --- | --- | --- |
| SA-02 development protections | Private GitHub Free and manual founder review approved under D100. Local staged scanner active. [PR #4](https://github.com/cpuglis1/daylight-medicare/pull/4) merged on November 7. GitHub verified private `main` at `ebced4e67b1e6c76dcb6c58d428ce7907cc3de26`. Both push checks and initial Dependabot scans passed. | Observe the first scheduled audit and confirm personal Actions billing settings. The original checkout's older index still needs deliberate publication-policy reconciliation. |
| SA-27 pilot amendment | [Security spec §8.1](../../docs/company/LAUNCH_SECURITY_SPEC_2026-11-06.md#81-proposed-invite-only-gate-1-amendment--november-7-2026) records the approved manual repository review exception and $100 budget. | Approve the remaining exact scope and deferrals. The 20-participant limit is a rehearsal bound. |
| SA-26 invitations | Signed expiring link fragments, one redemption, distinct browser bindings, and revocation checked on each protected request. Founder CLI can issue a fresh invite for an approved share. | Verify key management, link delivery, expiry and reverse proxy redaction on the deployed target. |
| SA-06 cost and stop controls | Separate durable ledger, one $100 cumulative ceiling, settled and held amounts attributed to participants. Concurrent reservations cannot consume the same balance. Guest/all-chat switches checked before dispatch. Paid feature routes are disabled in the rehearsal. | Wire the approved model client, including the token counting path, into a production entry point. Verify provider limits, spend alerts, price/usage reconciliation and deployed switches. Paid-feature switch exercise needs an applicable route or recorded scope exclusion. |
| SA-11 web | Same-origin requests, CSRF, restricted route set, Secure/HttpOnly/SameSite cookies, inherited strict CSP and plain-text model rendering. Existing provider transport has a fixed HTTPS endpoint list and disallows redirects. Verified TLS 1.2 with HSTS over local HTTPS. Invitation-bound pacing enforces the 3-second gap, 10 messages per rolling minute and one in-flight turn within the rehearsal process. | Check the real origin, load and request bounds, provider egress and log redaction. Hosted pacing must enforce the same limits across the actual worker layout. |
| SA-12 profile isolation | HTTP rehearsal blocks saved-profile endpoints and rejects a different participant's guest session. A new PostgreSQL migration passed two-beneficiary read/write checks and immediate revocation in a disposable cluster. | Integrate the approved saved-profile service and rerun A05 on the target before enabling saved profiles. Keep access checks and database reads in short transactions. |
| SA-01 staff access | PostgreSQL test verified a scoped staff gateway can produce a content-free access receipt and lacks direct profile-table read access. | Sign the [official designation](../../docs/company/security-program/HP-01_SECURITY_PRIVACY_OFFICIAL_2026-11-07.md), configure and verify console passkeys, recovery and least-privilege accounts. Bind verified staff identity at the gateway and commit the audit receipt before disclosing a record. Never give staff interactive SQL access using that gateway role. Review access monthly and remove access the day someone leaves. |
| SA-17 pilot spend evidence | Operator reports use settled and held amounts, participant counts, observed completion, median and maximum, and incomplete or unclassified cost. Rehearsal treats each invitation as one reporting visit. A zero completion count returns an unavailable cost per completion. | Capture actual founder-observed supported completions and reconcile provider bills. Report the cohort size and keep small-sample estimates provisional. |

The remaining deployment gate also needs the selected host and approved model
vendor, exact data handling and retention, redaction before all model transfers,
and verification of service-area and other pilot scope checks. The rehearsal
blocks paid provider use, legacy model routes, saved profiles and paid actions.
Profile and audit SQL were applied only to a disposable PostgreSQL cluster.

## Rehearsal entry points

Run from `alternatives/advisor-first` with a fresh private state directory outside
the repository. Use fictional inputs and UTC epoch expiry values.

```sh
python3 pilot_admin.py /private/tmp/daylight-fictional-pilot initialize END_EPOCH
python3 pilot_admin.py /private/tmp/daylight-fictional-pilot issue INVITE_EXPIRY_EPOCH
python3 server.py --port 0 --fixture --pilot-state /private/tmp/daylight-fictional-pilot
```

Open the issued private path on the printed loopback origin. The invitation is a
bearer secret. Use `switch guest_chat on` and `switch all_chat on` for fictional
chat. Both start off. Use `revoke PARTICIPANT`, `usage`, `complete PARTICIPANT`
and `session-costs` through `pilot_admin.py` for the founder workflow. Optional
TLS uses `--pilot-tls-cert` and `--pilot-tls-key` with a trusted loopback test
certificate. The fixture requires isolated files and refuses provider clients or
research repositories. No raw chat enters the cost ledger.

## Checks run

- 136 tests passed across pilot security, advisor budget, provider budget,
  fake-provider HTTP, session recovery HTTP and natural agent. Credentials were
  removed and the harness denied external sockets and subprocesses.
- The existing operations suite and new pilot profile SQL assertions passed on
  PostgreSQL 16.8. The cluster had TCP disabled and was removed after the test.
- Local HTTPS negotiated TLS 1.2 with hostname verification and returned HSTS.
- In-app browser checks covered 1280, 768 and 390 pixel widths. Redeeming a
  fictional invitation navigated to the advisor and made Get started available.
- Both hosted [repository](https://github.com/cpuglis1/daylight-medicare/actions/runs/42421431885)
  and [dependency](https://github.com/cpuglis1/daylight-medicare/actions/runs/42421431888)
  push checks passed at the merge commit. GitHub reported successful
  [Python](https://github.com/cpuglis1/daylight-medicare/actions/runs/42421436401)
  and [Actions](https://github.com/cpuglis1/daylight-medicare/actions/runs/42421436079)
  Dependabot runs and zero open dependency alerts at the time of verification.
  Scheduled execution and account billing are separate observations. The P0
  rehearsal is local code and is separate from PR #4.
- After adding invitation-bound pacing, 54 pilot security, pilot scope,
  response failure, advisor budget and provider budget tests passed with no
  external sockets or credentials. The final six-test pilot security run passed
  with the HTTP check renewing the guest cookie and verifying the same invite
  was still rate limited.
