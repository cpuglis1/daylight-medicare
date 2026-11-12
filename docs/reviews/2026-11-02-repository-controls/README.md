# Repository controls: execution record

Completed November 2, 2026. The owner requested free ongoing checks beginning with step 1, the reviewed reproducible GitHub baseline, and assigned maintenance to **@cpuglis1; specialist roles pending**.

The bounded 12-file controls package is merged through [PR #1](https://github.com/cpuglis1/daylight-medicare/pull/1). Commit `3eaf0f81e18fb39603e3ec7775925576fe27c3b5` has tree `5ae8da67192899da6073e43f800954c1914e8c46`, exactly matching the locally reviewed candidate. This completes the first controls increment, not the full current-advisor source handoff.

## Verified execution

- **46 offline tests passed** in the isolated controls checkout; the same suite and candidate checks passed on GitHub's clean Python 3.12 runner. [PR run](https://github.com/cpuglis1/daylight-medicare/actions/runs/41516042206) and [post-merge main run](https://github.com/cpuglis1/daylight-medicare/actions/runs/41516208692) both succeeded.
- Independent code review reproduced and closed four defects: owner-file deletion, CODEOWNERS rule overrides, premature ignored-file reads, and policy edits making inherited files eligible without inspection. Regression coverage also includes staged-versus-working-file differences, intermediate removed secrets, engine pins, symlinks, parser redaction and newly ignored files.
- Staged and outgoing-commit checks pass for the 12 selected files. The full snapshot audit reports **126 metadata findings** among 231 tracked files. These include archives, bulk artifacts and files outside the candidate policy. They are review obligations, not 126 confirmed leaks. No content-level secret or syntax findings were added by that bounded full-snapshot check; this does not prove historical absence of secrets or personal data.
- Actual `main` protection requires pull requests, up-to-date `repository-checks` from GitHub Actions app 15368 and resolved conversations. Force-push and deletion are disabled; administrators are subject to protection. Zero independent approvals are required while only one maintainer is assigned. An administrator can still change repository settings.
- Native GitHub secret scanning and push protection were already enabled and remain enabled. Vulnerability alerts and Dependabot security-update proposals were enabled during this work. Weekly GitHub Actions dependency proposals are configured, with no auto-merge.
- No customer stores, Medicare source archives, app runtime, evidence acceptance or cloud resources were changed. The selected publication contains newly authored technical controls and documentation, no customer/evidence dataset or third-party asset payload.

## Local and remote state

The original working folder remains at `7d15873e98875dca7940d07903c141d19d5da333`; its Git index remains empty. The 12 local control files match the published versions, but were not bulk-staged or merged into the existing dirty local checkout. The remote has the additional merged controls commit. Reconcile local work deliberately; do not use a reset or blanket add/pull to resolve this distinction.

The optional executable pre-commit hook is supplied, but **not installed in the original working folder**. Install it in a clean contributor checkout using the [operating guide](../../project/REPOSITORY_CHECKS.md), preserving any existing hooks. GitHub protection is active regardless of local hook installation.

The review checkout at `/private/tmp/daylight-repository-controls-20261102` used shared local Git objects for bounded candidate construction; it is not an off-machine recovery copy. GitHub's successful hosted checkout independently verified that the published controls run without the founder's local app/data directories. It did not launch the current advisor or restore a database.

## Durable records and next work

See [exact file manifest](publication-manifest.json), [candidate tree](candidate-tree.json), [staged check](staged-check.json), [outgoing revision check](revision-check.json), [full snapshot findings](full-snapshot-check.json), [test log](tests.txt), [activation/settings receipt](activation.json), [before settings](settings-before.json) and [protection request](protection-request.json). Targeted local documentation changes and their before-images are recorded in [the local change manifest](local-document-changes.json).

Next step-1 work remains: review the inherited publication/history backlog; select the current advisor source and close exact dependencies; provide permitted fictional development fixtures; lock dependencies; prove a fresh-clone application launch; and assign the additional technical, evidence, privacy, consumer-release and recovery reviewers. Current data/source holds and the frozen L03 scope remain unchanged. The controls provide repeatable technical evidence, not domain acceptance or consumer readiness.

Operationally, review failed PR checks and Dependabot proposals as they arrive, inspect the Security tab, and revisit actual ownership and branch protections when contributors or settings change. The operating guide maps the later restore, evidence, release and study controls; those are not claimed implemented here.
