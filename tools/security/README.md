# Dependency and developer protections (SA-02 / D98)

Use `python3 tools/install_git_hooks.py` to activate the existing staged-blob
scanner. It refuses to replace another configured hook directory or existing
executable hooks. It neither stages files nor reads working `.env`/customer
stores. The checker inspects the policy and files in the proposed Git snapshot;
that snapshot must include the existing policy/ownership files. The original
dirty workspace's old index does not yet contain them, so an attempted commit
there fails closed until a deliberately reviewed source commit supplies them.
Do not use a blanket `git add` to resolve this. Clean current-remote checkouts
already include these files. Hooks can be bypassed; they are not server policy.

## Dependency auditing

In an isolated environment, install tools with:

```sh
python3 -m pip install --require-hashes -r tools/security/requirements.lock
python3 -B tools/audit_dependencies.py --output-dir /tmp/daylight-dependency-reports
```

The audited inventories are the research requirements lock, this tool lock and,
when present, the separate plan-types runtime lock. The script validates exact
pins, rejects requirement URLs/includes/options, checks tool input/lock parity,
and calls pip-audit with strict collection, no dependency resolution and no
project installation. Only public package identifiers/versions are queried.
Unknown packages, service failures, missing reports and known vulnerabilities
produce a failing result. Reports contain the exact inventory hashes, package
counts, JSON findings and CycloneDX ingredient lists. No `--fix` or ignore list
is used; changing a runtime/engine lock still requires its normal review.

Coverage is the named pinned inventory, not a claim of every installed runtime
component. The locally added operations package's optional Postgres extra is
not a separately resolved deployment lock yet; archived prototype dependencies,
container/system packages and a deployed image inventory are outside this audit.
Resolve/pin/audit those before releasing the corresponding component. An SBOM
from a requirements file is not proof that a deployed image matches it.

The new `dependency-security` workflow runs on PRs, `main`, weekly, manual
dispatch and published releases. It uses read-only permissions, immutable action
revisions, no production secrets and hash-verified tool installation. It retains
reports as artifacts for 90 days even on failure; a missing artifact is an error.
Before accepting a release, copy its exact-SHA reports into the durable release
evidence archive; GitHub artifacts expire. This workflow neither publishes a
release nor authorizes one. Existing repository checks remain intact.

Dependabot proposes weekly updates for Actions, research Python dependencies and
the audit-tool input. Review and regenerate affected locks before merging;
input/lock mismatch blocks the audit. No auto-merge or untrusted project-code
execution is enabled. Add a pip directory when a new independently deployed
manifest is deliberately published; uncommitted local files are not monitored
by hosted Dependabot.

Refresh the audit tool lock in an isolated **Python 3.12** environment with
pip-tools 7.6.2, matching CI's Python minor version:

```sh
pip-compile --generate-hashes --allow-unsafe --strip-extras --no-emit-index-url --no-emit-trusted-host --output-file tools/security/requirements.lock tools/security/requirements.txt
```

Review changed packages/hashes, repeat the audit, and verify a clean Linux/Python
3.12 CI install. Compilation on the workstation alone is not runner verification.

## Enforcement and review

GitHub is private. The protection API returned HTTP 403 on November 7, requiring
GitHub Pro or public visibility. Keep visibility unchanged. After the owner
decides the plan, require `repository-checks` and `dependency-security` from
GitHub Actions, strict freshness, PRs, resolved conversations, no force-push or
deletion and enforcement for administrators. The only assigned maintainer is
@cpuglis1. Do not claim independent approval until another reviewer is assigned.
The proposed temporary founder-review procedure and plan purchase remain owner
decisions in the stage-1 packet. CI passing is not enforced branch protection.

References checked November 7, 2026: [pip-audit](https://github.com/pypa/pip-audit),
[Dependabot configuration](https://docs.github.com/en/code-security/reference/supply-chain-security/dependabot-options-reference),
[GitHub protected branches](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches).
