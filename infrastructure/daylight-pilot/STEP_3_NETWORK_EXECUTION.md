# Step 3: closed network migration completed

November 18, 2026, 6:54 p.m. Eastern · D193.

The owner confirmed both network changes at action time. Both guarded CloudFormation updates completed and passed their live verification. NAT was removed, the route now uses the existing internet gateway, and the existing allocated IPv4 was attached to the same host. No server, disk, role, key or bucket was replaced. The security group retains zero inbound rules. The host is publicly addressed but does not serve public traffic.

The two encrypted disks (50 GiB total), network interface and standard CPU-credit setting were verified. A fresh Systems Manager command returned `daylight-network-ok`, status Success and response code 0, confirming administrative connectivity after the change.

[Observed execution receipt](pro-network-execution-20261118.json) records the exact reviewed plan hashes, change-set identifiers, verification times and preserved resource IDs. Full generated evidence remains in `/home/cloudshell-user/daylight-pro/pro-migration-evidence`. The original preparation archive and its manifest remain unchanged historical artifacts.

## Costs and remaining work

Removing NAT reduces the estimated baseline by $32.85/month at 730 hours, from $72.27 to $39.42. CloudFront Pro has not been purchased; the proposed $15 subscription would bring that baseline to about $54.42. Usage, tax and origin-certificate issuance/renewal are separate. These are estimates, not a whole-account spending cap.

No application, API key, DNS change, certificate, CloudFront distribution, WAF ACL or Pro subscription was deployed in this step. Daylight is not live at the domain. The next work is Pro eligibility/subscription, DNS/TLS, authenticated origin proxy, hosted runtime integration, persistent consented history, bounded backups/logs and the shared AI allowance. Inbound access stays closed until the origin and release safeguards are verified. Pending subscription creation can incur WAF pay-as-you-go fees; disclose those before creating the edge stack.

## Verification performed

- Revalidated exact plan hash, live template, identities, parameters and AWS change set immediately before each execution.
- Verified the first update before preparing the second; second preview contained only the existing address association.
- Ran `verify remove-nat` and `verify attach-address`, both successfully.
- Sent one non-sensitive Systems Manager connectivity command and read its successful result. No model calls or app conversation tests.

The 24 offline tests passed before this session; no implementation changed and no offline tests were rerun during execution. DNS lookups and Pro subscription eligibility remain unverified from the earlier preflight.
