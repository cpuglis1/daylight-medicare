# Pilot security stage 1: drafts and development protections

November 7, 2026 · D98 · SA-27 / SA-02 / SPEC-D3–D5; SA-01 preparation.

## Ready for owner decisions

- [Concrete approval packet](DECISIONS.md): 20-person invite-only scope through
  December 23; exact temporary deferrals; $100 provider ceiling / $90 usable
  pilot model budget; numeric usage logging and retention; private GitHub plan
  and review procedure.
- [Spec §8.1 draft amendment](../../company/LAUNCH_SECURITY_SPEC_2026-11-06.md#81-proposed-invite-only-gate-1-amendment--november-7-2026).
- [Typed logging proposal](LOGGING_PROPOSAL.md), including the separate unresolved
  study-transcript decision. No logging or transcript retention was activated.
- [Draft development-controls PR #4](https://github.com/cpuglis1/daylight-medicare/pull/4).
  Merge/review is still pending; the new scheduled/default-branch controls do not
  become active on `main` until it is merged.

## Installed and prepared

The original workspace now has local `core.hooksPath=.githooks`. The existing
pre-commit scanner checks staged blobs for likely secrets, forbidden publication
paths, syntax and integrity. Installation preserved the original Git index and
found no prior executable hooks or custom hook path. The new installer refuses
to replace either in other checkouts. Tests prove that a cleaned working copy
cannot hide a staged fictional credential, and matched values stay out of output.

The original workspace's old Git index lacks the canonical publication-policy
files. Its hook therefore fails closed until a deliberately reviewed snapshot
includes them. No unrelated file was staged to “repair” that state. The isolated
current-remote checkout already has the policy, and its selected staged/outgoing
checks pass. Local hooks can be bypassed; they are not server enforcement.

Nine selected developer-control files are prepared in `codex/pilot-security-stage1`:
safe hook installation, strict pinned-inventory auditing, nine fictional failure
probes, hash-locked audit tooling, the separate `dependency-security` workflow,
Python Dependabot proposals and operating instructions. The workflow runs on
PRs/main, weekly, manual dispatch and release publication. It outputs JSON
vulnerability reports and CycloneDX SBOMs with exact inventory hashes, with
read-only repository access and no production credentials/project installation.
No runtime dependency or protected engine lock was changed.

The PR additionally contains a minimal test-only clock correction in
`alternatives/advisor-first/tests/test_provider_http.py`: fake-provider tests
use the pricing fixture's verified date rather than today's date. The local
workspace already had the equivalent clock fix with a newer pricing API; its
test file was not changed or copied wholesale into the older remote source.
The PR therefore contains ten selected files, with no production budget change.

GitHub vulnerability alerts and automated security-update proposals were already
enabled and were verified. Actual repository visibility is **private**. The
`main` protection endpoint returned HTTP 403 requiring Pro or public visibility;
no purchase, visibility change or branch-policy change was attempted. Native
secret-scanning/push-protection metadata is unavailable, so those features remain
unverified. The unapplied [protection proposal](protection-proposal.json) requires
PRs, both checks and conversation resolution, prohibits force-push/deletion and
applies to admins. Its zero independent approvals reflects the sole assigned
maintainer; the owner must decide that temporary review procedure or assign a
second reviewer. This is not a claim that SA-02 is fully accepted.

## Verification

| Check actually run | Result / evidence |
| --- | --- |
| Existing local baseline-control regressions | 38 passed; [log](baseline-tests.txt) |
| New fictional hook/audit failure probes | 9 passed; [log](security-tests.txt) |
| All tool checks in isolated current-remote checkout | 59 passed; [log](clean-checkout-tests.txt) |
| Targeted fake-provider HTTP and budget regressions | 23 passed, including expiry/clock-rollback rejection; [log](fixture-tests.txt). Disposable ledgers, loopback-only networking and no provider credentials. |
| Selected staged and outgoing Git snapshot checks | Passed with no new findings; [staged](staged-check.json), [outgoing](outgoing-check.json). Inherited publication debt remains separate. |
| Existing remote research lock | 33 pinned packages, no known vulnerabilities; [report](remote-dependency-audit.json) |
| Current local research and plan-types locks | 38 packages in each inventory; no known vulnerabilities; [summary](dependency-reports/summary.json). Inventories overlap and are not summed as distinct dependencies. |
| Corrected audit-tool lock | 29 packages; hash-checked installation under Python 3.12; numeric package/SBOM results in the same summary. |
| GitHub dependency-security | Passed on the final PR revision under Linux/Python 3.12; [run](https://github.com/cpuglis1/daylight-medicare/actions/runs/42418185787), [downloaded summary](hosted-final-dependency-reports/summary.json). Downloaded artifact SHA-256 verified before saving all five reports locally. |
| GitHub repository-checks | Passed on the final PR revision; [run](https://github.com/cpuglis1/daylight-medicare/actions/runs/42418185711), [status receipt](hosted-checks.json), [test summary](hosted-tests-summary.txt). Includes existing fictional advisor, profile-contract, whole-offering and HTTP/asset checks. |
| Original workspace staging | Index SHA-256 unchanged from [before manifest](before-manifest.json); no reset, stash, blanket add or merge into the original workspace. |

The initial new hook test expected detailed error wording; the existing checker
intentionally returns a redacted configuration error. The test was corrected to
assert that safe contract. No security check was weakened to get a pass.

The first hosted dependency run failed because a Python 3.14-generated tool lock
omitted Python 3.12's `typing-extensions` dependency. Regenerated with Python
3.12, retained hash enforcement, verified isolated installation and reran CI.
The current lock includes 29 packages and passed the hosted audit. The artifact
upload action was also pinned to its current v6 commit to remove a runtime
deprecation warning. Application/research locks were left unchanged.

The broader hosted run then exposed nine pre-existing provider-fixture failures
among 786 advisor tests: the fixture used an expired pricing review with the
wall clock. Only the fixture clock was corrected, with no pricing extension,
production clock override, skipped test or weakened guard. The targeted 23-test
verification required permission to bind a disposable loopback port after the
default sandbox denied it; external network calls remained explicitly forbidden.

Actual commands included `python3 -B -m unittest discover -s tools/tests` with
the relevant test patterns; `tools/baseline_checks.py --staged` and
`--revision HEAD --base origin/main` in the isolated checkout; hash-verified
pip installation; and `tools/audit_dependencies.py --output-dir ...` under
Python 3.12. The hosted existing advisor suite uses fictional inputs, strips
provider credentials and denies external Python network access. No paid model
probe or live participant conversation was run.

## Limits and remaining work

1. Owner approval of the exact scope, budget, logging contract and account/review
   choices; no exception or new spending/retention is effective yet.
2. Review/merge PR #4, then confirm default-branch Dependabot/schedule operation.
   Plan upgrade is needed for server-enforced required checks on this private repo.
3. SA-01 personal passkeys/recovery and founder access review; production access
   roles/customer-access logging remain next-stage work.
4. SA-11/26/12/06 implementation, deployed verification and SA-17 metering before
   pilot traffic. Current best-effort diagnostic traces are not a spend ledger.
5. Resolve the operations package's optional Postgres deployment lock, deployed
   image/OS inventory and any separately shipped components. Current audits cover
   only explicit pinned inventories; they are not a whole-production supply-chain
   audit or guarantee that no vulnerability exists. No dependency upgrades were
   auto-applied. Preserve sealed historical lock bindings.
6. Store exact-release SBOM/check evidence durably before GitHub artifacts expire
   after 90 days. The workflow is not a release-approval mechanism.

Source/recommendation acceptance, the 41 conditional meanings, source STOPs,
protected variants and stores, existing local spending limits, D64/D73 and
independent review/release gates remain unchanged. No cloud provisioning,
customer-plane schema migration, AI-provider account change or invitation
sending occurred. Changes were made with targeted patches and a ten-file
isolated development branch; the full working folder was never published.
