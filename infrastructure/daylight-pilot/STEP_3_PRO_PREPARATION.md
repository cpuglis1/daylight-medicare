# Step 3: CloudFront Pro migration preparation

November 18, 2026 · D193. Local implementation complete; AWS validation and
execution blocked by concurrent Firefox use and a browser-control timeout.
No successful AWS preflight result was observed. No infrastructure mutations,
subscription, certificate request, DNS edits or paid model probes were made.

The owner said “okay continue!” after the $15 Pro proposal, ~$54.42/month
baseline and $7 origin-certificate issuance/renewal disclosure. Continue with
that scope. D191 still prohibits undisclosed paid additions or automatic
upgrades. Browser action-time confirmation remains necessary before changing
network isolation or opening inbound access; preparation is not blocked on it.

## What was built

- `build_pro_migration.py` generates three exact network stages and a closed
  edge template in `pro-candidates/`. It makes no AWS calls.
- `pro_migration_control.py` prepares, inspects, executes and verifies one of
  the first two network stages at a time. Account, region, live template,
  resource identity, change-set contents and parameters must match the plan.
  An exact plan hash is required for execution. Unexpected resources or
  replacements are rejected. There is no automatic next stage or retry.
- `pro_preflight.py` performs only account/resource reads, template syntax
  validation, managed-policy checks and public DNS lookups. It does not
  purchase or approve a subscription, request certificates or read secrets.
- `test_pro_migration.py` adds 16 offline preservation/rejection checks. With
  the existing eight foundation tests, **24 passed**. Python compilation passed
  for all three new scripts. These tests do not establish cloud acceptance.

## Exact migration stages

| Stage | Expected resource changes | Access and costs |
| --- | --- | --- |
| `remove-nat` | Remove `NatGateway`; modify only `PrivateRoute` to the existing internet gateway | Keep existing allocated IPv4, server, disks, key, bucket and roles. Zero inbound rules. SSM temporarily loses its route while the server has no public IP. NAT billing stops after deletion completes. |
| `attach-address` | Add `OriginAddressAssociation` using the existing allocated IPv4 | No additional IP or replacement server. Zero inbound rules. Verify SSM returns and disk/host/ENI identities are preserved. |
| `cloudfront-ingress` | Modify only `HostSecurityGroup` to allow TCP 443 from the verified AWS CloudFront prefix list | Candidate only; controller deliberately cannot prepare or execute this stage. Requires a tested TLS proxy, distribution token, cost controls and action-time approval. |

NAT removal and IP association are separate updates to avoid racing for an IP
still attached to a deleting NAT. There is no application on this host yet, so
the temporary SSM interruption does not interrupt a pilot. Do not start stage
one unless able to finish stage two in the same operator session. These stages
change the application subnet from private routing to public routing; subnet
logical IDs are retained to avoid replacing the host. Both stages retain zero
ingress; a public IP alone must not open app/SSH ports.

The first two stages do not subscribe to Pro or issue a certificate. After
them, the monthly network/host baseline would be ~$39.42 at 730 hours; the
proposed later $15 subscription yields ~$54.42. These are estimates, not a
whole-account cap. Currently the original ~$72.27 foundation remains deployed.

## Closed edge and billing boundary

`closed-edge.json` specifies one disabled distribution, a WAF ACL whose default
action blocks every request, managed zero-TTL caching, AllViewer forwarding,
HTTPS-only origin, a NoEcho origin-token parameter and PRO/DEFAULT only. It has
no traffic activation action, logs, Lambda@Edge, extra server or automatic tier
upgrade. Unsupported HTTP methods must still be rejected by the proxy/app:
CloudFront's method selection requires the seven-method set to support POST.

AWS documents that a CloudFormation paid subscription starts in
`PENDING_APPROVAL`. While pending, underlying resources are billed pay-as-you-go.
In particular, the WAF ACL can accrue its base fee even while the distribution
is disabled. **Do not describe pending creation as free or create that edge
stack until the interim billing has been priced/disclosed.** Require observed
ACTIVE PRO pricing before allowing public traffic. A retained subscription
requires deliberate cancellation; deleting the stack is not a cost stop.
[AWS subscription resource and billing states](https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-resource-pricingplanmanager-subscription.html).

No source token or API credential is in the bundle. The viewer certificate
must be issued in us-east-1 for both public hostnames before using the edge
template. Origin certificate deployment/renewal and the origin-token proxy
are not yet implemented. A 60-second candidate origin timeout does not solve
long model requests; fictional delay/recovery verification remains required.

## Next operator session

Use the bundle listed in `pro-preparation-manifest.json`, upload it to the
existing workload CloudShell and extract it into a new `daylight-pro` directory.
First confirm its SHA-256 matches the manifest. No credentials need to be
copied into this repository or chat.

Run `python3 pro_preflight.py` first. Stop on any failure or unexpected live
template. Save its output. Syntax validation is not paid-plan eligibility.
Then `python3 pro_migration_control.py prepare remove-nat`, followed by
`python3 pro_migration_control.py inspect remove-nat` once the change set is
ready. These steps do not execute resource changes. Review the exact cloud
diff and obtain the required action-time confirmation for the two closed
network changes before any `execute` command.

After execution, use the matching `verify` action, then separately prepare and
inspect `attach-address`. The controller accepts an execution only with
`--reviewed-sha256` equal to the printed plan digest. Do not substitute the old
foundation controller or rerun its CREATE command. A failed stage needs
inspection. The execute call explicitly sets `DisableRollback=True` so failure preserves the partial state for inspection instead of automatically recreating the NAT gateway. Recovery is a separate reviewed operation.

Before public ingress, implement and verify the remaining proxy authentication,
outbound usage limits, bounded backup/log jobs, restricted routine deployment
permissions, provider/shared AI ledger binding and durable consented history.
Neither this bundle nor the existing app provides a guaranteed AWS invoice cap.

## Evidence and limits

Test command: `python3 -m unittest test_foundation.py test_pro_migration.py`.
Result: 24 passed, zero failures; all offline. Compilation:
`python3 -m py_compile build_pro_migration.py pro_migration_control.py pro_preflight.py`.
Generated candidates are checked against source in the test suite.

The browser showed authenticated workload CloudShell, but the read-only command
did not yield a result. A subsequent interaction was stopped because the user
changed Firefox windows. A later state read timed out; reconnecting showed a
different active window. No AWS results are inferred from those attempts.
Bring the workload CloudShell window to the foreground for the next short
verification session. Existing foundation resources continue accruing charges.
