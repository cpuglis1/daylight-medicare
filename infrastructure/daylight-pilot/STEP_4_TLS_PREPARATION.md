# Step 4: CloudFront Pro active; HTTPS certificates issued

November 18, 2026, Eastern · D194. **The application is not live.** Pro and TLS setup completed; the existing server remains closed. This supersedes the pending-validation/login status in `tls-preparation-20261118.json`, preserved as historical evidence.

The owner continued after the disclosed $15/month Pro price, $7 origin-certificate issuance/renewal and at-most-$0.25 temporary WAF setup allowance. Estimated hosting baseline is now **$54.42/month at 730 hours**, before remaining usage/tax, with a separate $20 cumulative model allowance. No higher tier or additional hosting resource was purchased. This is not an AWS invoice cap. Actual billed setup charges have not been reconciled.

## Verified live

| Item | Result |
| --- | --- |
| Pro subscription | PRO, ACTIVE; activation updated at 7:16 p.m. Eastern |
| Edge stack | daylight-pilot-edge, CREATE_COMPLETE; exactly three added resources |
| Distribution | EHF4UYWRJHWYV, d95tkkq6lwfvh.cloudfront.net; Deployed but disabled |
| Firewall | Default block; no allow rules; sampling disabled |
| Server | Same instance and disks; zero inbound rules |
| Viewer certificate | ISSUED for root/test; not exportable |
| Origin certificate | ISSUED for origin.daylightmedicare.com; key not exported |
| DNS | Three validation CNAMEs saved/read back; matching public resolver answers |
| Mail/web routing | MX, DKIM and root redirect preserved; traffic DNS unchanged |
| Host prerequisites | Python 3.11.18, PostgreSQL 18.6, nginx 1.30.6 and nftables installed from official Amazon Linux packages; nginx/PostgreSQL inactive |
| Provider credential | Existing secret has no versions; API key not installed |

[Execution receipt](pro-edge-execution-20261118.json). Full readbacks are in `/home/cloudshell-user/daylight-pro/edge-evidence/`, including `closed-edge-verified.json`, `pro-approval.json` and `runtime-access-review.json`. Local receipts are selected UI transcriptions, not raw API exports.

## DNS validation and subscription

Keep these records for renewal:

| Type | Namecheap host | Target |
| --- | --- | --- |
| CNAME | `_e74775961994b67300b4777580f260f3` | `_a1d8fdb950b2c0315c369d113759001b.wzccmgtwzk.acm-validations.aws.` |
| CNAME | `_8834cc9a8ad2890c7cbb084c26aa3805.test` | `_9856db689537e79d2a72d621d352802d.wzccmgtwzk.acm-validations.aws.` |
| CNAME | `_978352daa92bc5f3ca5496f6ddcf8403.origin` | `_1d47c612a0eda61aa62d40390a73c83b.wzccmgtwzk.acm-validations.aws.` |

SDK service: `pricing-plan-manager` (boto3 1.43.83). Paid subscription was created PENDING_APPROVAL, inspected as PRO, explicitly approved, then verified ACTIVE. The earlier archive's misspelled SDK name remains historical; current `pro_preflight.py` is corrected.

## Private package and reviewed permission

Built `daylight-rehearsal-20261118.tar.gz`: 357 files, 17,981,238 bytes, SHA-256 `aaa19850dd02ccd61b25f633e170bc8f01d0321cbe26e5b1715874e2cfe3ec42`. Existing packager verified evidence/backup hashes. A bounded scan found no matching OpenAI secret, AWS access-key ID or private-key header in selected text files; this is not a complete security audit. The archive contains restricted display evidence and remains private.

Uploaded through CloudShell and staged in the existing private KMS-encrypted bucket at `deployment/rehearsal/<sha256>.tar.gz`. Readback verified byte length, SHA-256 metadata, KMS encryption and bucket key. This is a rehearsal artifact, not a release with live chat or durable transcript integration. Its temporary staging object uses the bucket's existing expiry policy, not a permanent release registry.

`build_runtime_access.py` generates `runtime-access.json`. Three offline checks passed: resource preservation, exact read-only scopes, and rejection of extra resources/replacement/ingress in the preview.

Prepared in this step and subsequently confirmed/executed in [Step 5](STEP_5_PRIVATE_INSTALL.md), change set:

`arn:aws:cloudformation:us-east-1:020055445580:changeSet/runtime-read-access-20261119/aa6750d7-2f34-48cc-8d7c-fab2b231be45`

AWS reports CREATE_COMPLETE / AVAILABLE and exactly one modification: HostRole.Policies, replacement False. Template SHA-256: `8e5a31e27f5d0ab5a7a588ec969ae2289508cbd707385ff826fcc4edea51fda7`.

It permits the existing host to read only the staged S3 object's exact key, decrypt through S3 with the existing KMS key/bucket context, and describe/retrieve/export only its origin certificate. Private-key handling can then occur locally on the host. It grants no bucket listing/writing, other objects/certificates, public ingress, new machines or subscriptions. Existing provider-secret permissions stay unchanged.

The browser-control policy required action-time confirmation for this IAM expansion. The owner subsequently confirmed it, and Step 5 records execution and readback. The pre-execution template matched `pro-candidates/attach-address.json`; the current foundation now matches `runtime-access.json`. Preserve this added policy in later network changes.

## Remaining launch work

Step 5 subsequently initialized the state disk and installed the private code, exact runtime, origin TLS and verified database. The app is still not serving visitors. Remaining: Linux restore/parity, origin TLS installation/renewal and origin-header delivery, hosted :8895 feature integration, reusable invitations, consented 90-day transcripts with deletion/backup controls, shared $2/$20 ledger, dedicated provider project/key/settings, bounded egress/logs/backups, test/pilot isolation and deployment/rollback automation.

No paid model call or live conversation ran. Traffic DNS, CloudFront enablement and CloudFront-only HTTPS ingress remain unapplied. Complete exact hosted release checks before visitors. Issued certificates and an ACTIVE subscription do not constitute a deployed application.
