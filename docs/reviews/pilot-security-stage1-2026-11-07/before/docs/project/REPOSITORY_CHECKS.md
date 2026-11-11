# Repository checks and ownership

**Current setting · November 2, 2026:** GitHub now reports this repository as **private**. Its protection endpoint returns HTTP 403 requiring GitHub Pro or public visibility, so required-check/PR enforcement is unavailable on the current private-repository plan. CI still runs; maintainers must check the results before merging. Native secret-scanning/push-protection status is not currently verifiable: the repository API returns no security-analysis metadata. The local/CI pattern scan remains active. No visibility, plan or billing change was made. The publication policy retains its stricter public-content review boundary; it does not control actual repository visibility.

Owner direction, November 2, 2026: begin the free ongoing controls for a reviewed, reproducible GitHub baseline. Route repository maintenance to **@cpuglis1**; specialist roles remain pending. This is step 1 of collaboration readiness, under D64/D73/D85 and company capabilities 10, 13 and 15. The first consumer target remains a 2026 controlled Collier County pilot.

## What runs

| Control | When | What it establishes |
|---|---|---|
| Repository checks | Every pull request and push to `main`; manual dispatch | Control regression tests; changed Git blobs and outgoing commits checked for restricted paths, bulk artifacts, likely credentials, Python/JSON syntax, ownership consistency and engine pins when present |
| `repository-checks` status | Every PR/main run; maintainer checks before merge | The proposed change passed the configured checks; server enforcement requires a supported protection plan |
| CODEOWNERS and owner registry | Every change | @cpuglis1 is the maintenance contact; specialist vacancies stay explicit |
| GitHub secret scanning and push protection | Where supported by the plan and settings | Verified enabled at the earlier public activation; currently unverified in the private setting. Local pattern checks run independently |
| Dependabot | Weekly for GitHub Actions; supported security advisories | Proposes dependency changes for review; never automatically merges |
| Optional local hook | Before a local commit, after installation | Checks the index before publication; never stages files |

The workflow uses a standard `ubuntu-24.04` runner, SHA-pinned actions, read-only repository permissions, no stored credentials, and a ten-minute timeout. It installs no project dependencies and invokes no AI, database or cloud service. Standard GitHub-hosted Actions runners are free for public repositories. This repository is currently private, so its plan’s included minutes and existing billing limits apply; unlimited free public-runner usage cannot be assumed. See [GitHub billing](https://docs.github.com/en/actions/concepts/billing-and-usage) and [public branch-protection availability](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches).

## Use the controls

From a checkout containing these files:

```sh
python3 -m unittest discover -s tools/tests -v
python3 tools/baseline_checks.py --staged
python3 tools/baseline_checks.py --revision HEAD --base origin/main
python3 tools/baseline_checks.py --revision HEAD --full-audit
```

The staged command inspects the index, including its own policy and ownership files. Unstaged fixes do not make a staged defect pass. The revision command checks the final snapshot plus changes in commits after the specified base; the base must belong to the checked history. A manual GitHub dispatch normally checks the latest commit range; select `full_audit` to inspect every current file. A full snapshot audit is not a complete historical secret audit.

Exit `0` means the selected technical checks passed; `1` reports findings; `2` means configuration or Git could not be checked. JSON reports contain rule/path/line identifiers, not matched credential values. Do not paste suspected credentials into a public issue. If a real credential has already escaped, revoke/rotate it and address its history; deleting the current line does not remove earlier copies.

For a new clean contributor checkout, inspect existing hook configuration before opting in:

```sh
git config --get core.hooksPath
git config core.hooksPath .githooks
```

Preserve any existing hooks instead of silently replacing them. Local hooks are a convenience and can be bypassed; protected GitHub checks remain the shared enforcement point. The original large working folder has not been reset or bulk-staged to install these controls. Use the reviewed remote branch in a clean checkout for collaborative work until its existing changes have been reconciled deliberately.

## What a failure means

Restricted paths, customer/session stores, local credentials, database dumps, PDFs and unreviewed bulk evidence do not belong in ordinary code commits. Keep them in the separately governed archive/data system. A publication-policy candidate still needs human review for personal information, publication rights and licenses. Pattern scans do not reliably discover arbitrary personal information or every secret.

An engine pin failure means the exact dependency is missing or changed. Restore the intended version or create a deliberately reviewed new engine revision; do not update hashes merely to make the check green. Ownership failures need an actual assignment or corrected registry. Specialist vacancies are reported and do not block maintenance-only changes; they do not grant permission to release specialist-dependent consumer capabilities.

Existing tracked bulk files are reported as inherited metadata debt during incremental checks. New or changed versions must pass. The full audit exposes that debt as failures; it is not silently waived. Green incremental CI is not a claim that the historical repository, current advisor or source archive has been fully reviewed.

Changing an already established publication policy requires a full snapshot review. A policy edit cannot make inherited files eligible without checking them or quietly erase the backlog. The initial controls bootstrap, whose parent has no policy, is explicitly an incremental introduction.

## Review and enforcement

Use a branch and pull request. Record scope, evidence, tests and remaining gaps in the PR template. Read the diff and outgoing history before merging, especially changes to these controls. Initially @cpuglis1 is the only assigned maintainer, so the intended branch policy requires PRs and passing up-to-date checks, but **zero independent approvals**. It must not pretend that an author approved their own work independently. Add a second qualified reviewer and an appropriate required-review policy when assigned. Domain acceptance remains separate regardless of GitHub settings.

The configured `main` policy should block force-pushes and deletion, require resolved conversations and the `repository-checks` status, and apply to administrators. A repository administrator can still change protection settings; periodic owner review is required. Verify actual settings in GitHub, not merely the existence of this document. No long-lived administrator credential is placed in CI to inspect itself.

Weekly maintenance is small: review failed runs and Dependabot proposals, inspect the Security tab, resolve or explicitly retain inherited publication debt, and verify protections/ownership when collaborators or settings change. Dependabot security coverage depends on committed supported dependency manifests; the current advisor dependency baseline is not yet fully published.

## Remaining step-1 work

This first increment publishes the controls themselves. The full current advisor still needs an explicitly selected source snapshot, dependency closure, fictional development data, complete dependency locks and a fresh-clone application launch. The earlier narrow developer rehearsal is useful evidence, not that complete result. Private/local-only evidence dependencies need an approved development export or fixture contract. Outgoing history, source-use rights and licenses require review. Assign domain/privacy/release/recovery owners and a second technical reviewer as people become available.

The next free systems follow the same pattern: isolated restore drills with manifests (step 2), source/condition/provenance reconciliation and freshness checks (step 3), exact-purpose release and reproducible-decision tests (step 4), and a prespecified study rubric with a failure register (step 5). They remain future work; this workflow does not validate those capabilities.

## Product and evidence boundaries

D73 review: the improvement is dependable contributor work. No consumer intake, education, comparison paths, commercial inputs, profile permissions, storage or UI changes are made. Existing recommendation/source holds remain in effect. No source acceptance is inferred, no frozen L03 denominator changes, and no customer information is moved. Technical execution evidence belongs with the exact reviewed commit; it cannot establish consumer comprehension, market completeness or recommendation readiness.
