# Step 5: approved server access, private TLS and verified database restore

November 18, 2026, Eastern · D194. The owner confirmed the exact permission preview with “yeah confirm.” The existing server can now read the single staged archive and its own origin certificate. The CloudFormation update finished UPDATE_COMPLETE; both its complete template and resolved IAM policy matched the reviewed scope. No public ingress, new service or subscription was added.

**The app is still not serving visitors.** Its code and data are installed privately; this is not the completed hosted chat runtime.

## What completed

- Downloaded the exact encrypted archive through the server role, verified its archive hash and all 357 member hashes, and extracted it privately under `/opt/daylight-pilot/releases/aaa19850dd02ccd61b25f633e170bc8f01d0321cbe26e5b1715874e2cfe3ec42`.
- Exported the origin certificate directly on the server. The temporary export passphrase and private-key contents were never printed or placed in SSM command arguments. Key files are root-only, mode 0600, under `/etc/daylight-pilot/tls`. Certificate/key match, expected hostname, expiry margin and system trust-chain checks passed. Proxy serving and automated renewal/reload are still pending.
- Installed Python **3.14.7** from the official Amazon Linux repository, plus the exact pinned Python dependencies in `/opt/daylight-runtime/venv-3.14.7`. The current default repository version is newer; the sealed data requires this exact version. No binding was relaxed or sealed manifest changed. `pip check` passed.
- Initialized only the verified empty 30 GiB encrypted state volume `vol-04a5e06e77ec054ac`, with checks against its serial, size, partitions, signatures and mounts. Mounted at `/var/lib/daylight-state` using its UUID and nodev/nosuid/noexec. The initial XFS command rejected an overlong label before formatting; a shorter label passed the same empty-disk guards.
- Restored into a new PostgreSQL 18.6 database. Existing restore targets are refused, and neither `--clean` nor source deletion is used. The original schema ACLs, immutable triggers, manifests and STOP records are retained; database ownership maps to the local PostgreSQL administrator. Reader roles are NOLOGIN. `daylight-postgres.service` uses a local Unix socket only, with a 768 MiB memory limit and read-only database default.
- Verified every column/row hash in all **eight CSG tables**, including **55,040 rate rows**, all **three Part D payloads**, snapshot identity, exact code/runtime bindings, reader SELECT privileges and absence of mutation privileges. The packaged advisor imports on Linux. No model or conversation probe ran.

[Observed execution receipt](private-host-execution-20261118.json). Full output is retained in CloudShell `edge-evidence/private-verification-result.json`; host receipts are `/var/lib/daylight-state/restore-receipt.json` and `restore-verification.json`.

## Checks and limits

Local verification: six archive checks (exact package, wrong hash, traversal/absolute paths and symlink rejection); one unittest covering six wrong/populated-volume cases; Python compilation; source-helper shell syntax. The successful on-host parity verifier is additional evidence. App-role HTTP behavior, end-to-end source STOP propagation and public TLS/cache/guest behavior have not been tested.

The original reconciliation attempt was blocked by local socket permissions. That
blocker is now cleared: the owner ran the read-only helper and
[source-reconciliation-20261119T004703168771Z.json](source-reconciliation-20261119T004703168771Z.json)
passes source controls, full CSG column hashes, PDP response/freshness checks,
and catalog/authority checks for snapshot
`b60269211a7896a80ae0f1ebe66af1be37a0a4f58fcd9d70ef15accf5b16b47c`.
No repeat owner action is required for this receipt.

## Continuation

Do not rerun the restore installer over the now-existing database. Use `verify_private_display.py` for read-only rechecks. The first restore script uploaded to CloudShell had the overlong label; the host and current local source use the corrected hash `6d494ca257e2bbe0d5095b1d3d7a5c4746f7fc4257786e7c123a02be3a225c68`.

The foundation now includes the added runtime-read policy. Any later ingress candidate must preserve `runtime-access.json`; applying the old whole `cloudfront-ingress.json` would remove the new policy. The prior migration controller intentionally refuses ingress preparation. Prepare/review the next exact delta from current state.

Hosted feature/history integration, reusable invitations and shared-ledger support are now implemented and tested; see [the follow-up evidence](../../audit-evidence/hosted-history-20261118/README.md). Remaining: installation of that revised runtime; production history, retention/deletion/backup verification; actual two-service binding to the shared $2/$20 ledger; dedicated OpenAI project/key/settings; least-privilege app login; origin-header delivery, proxy and renewal; egress/log/backup bounds; two-environment deployment/rollback; and hosted admission checks. CloudFront stays disabled, WAF blocks all, traffic DNS is unchanged, and the provider secret remains empty. Public exposure has not been confirmed or applied.
