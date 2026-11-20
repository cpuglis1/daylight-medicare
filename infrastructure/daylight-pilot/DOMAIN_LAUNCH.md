# Daylight domain launch

November 18, 2026. Implements D185–D187 and D191–D194 and carries forward D101, D141, D144–D145 and the existing source and participant release conditions.

Implementation has started. [Step 1 execution record](STEP_1_ACCOUNT.md):
the workload-specific Virginia exception was applied and verified on November 18.
The live inventory completed successfully, including EC2 and Secrets Manager.
The guarded scripts also passed 18 offline checks. No hosting resource or
DNS record was created in this step.

[Step 2 execution record](STEP_2_FOUNDATION.md): the closed private foundation
was subsequently created and verified. Charges have started. No application,
public ingress, CloudFront, WAF or DNS change was deployed. D191 initially paused further
provisioning. D193 continues the disclosed Pro migration; undisclosed paid
services, upgrades or expanded costs still require explicit approval.

D192 research: [CloudFront Pro feasibility](CLOUDFRONT_PRO_REVIEW.md) evaluates
a $15/month flat-rate edge with a restricted public origin and no NAT. It is a
candidate alternative. D193 directs continuing its implementation:
[staged migration code and current execution boundary](STEP_3_PRO_PREPARATION.md).
Both closed network stages subsequently completed with owner confirmation: NAT removed, the existing IP reused, storage preserved and SSM connectivity verified. Inbound access remains blocked. [Latest execution record](STEP_3_NETWORK_EXECUTION.md). Pro subsequently became ACTIVE under D194; the estimated baseline is now ~$54.42/month before usage/tax.

D194 now has Pro ACTIVE, both certificates ISSUED and three public DNS validation CNAMEs verified. Mail and traffic records are preserved. The distribution remains disabled and ingress closed. The exact host artifact/TLS read permissions were subsequently confirmed, applied and verified. Code, origin TLS, exact runtime dependencies and the display database are installed privately; full restore parity passed. No serving app or API key is configured. The owner-run source reconciliation receipt now passes; see `source-reconciliation-20261119T004703168771Z.json`. Hosted chat/history integration has since been implemented and checked, but is not installed as a serving production app. [Implementation and final-check results](../../audit-evidence/hosted-history-20261118/README.md). [Private installation](STEP_5_PRIVATE_INSTALL.md). [Current HTTPS execution record](STEP_4_TLS_PREPARATION.md).

The first release should be an invited demo at daylightmedicare.com, with test.daylightmedicare.com for checking the next release. Use the current :8895 experience as the feature baseline. The new `hosted_server.py` explicitly wires the newer conversation features and approved model to consented history and the shared ledger. It requires production provider settings, a credential and database roles before live activation; local research/recommendation-test routes are excluded.

## What the review established

- The Brain's infrastructure and privacy notes describe a prepared local deployment. November 12 produced the 195 MB display database, its approximately 12 MB compressed export and the unified local demo.
- The packaged hosted entry point explicitly requires fixture mode. Its systemd service restricts network access to localhost. Production model routing, exact hosted feature parity, Linux restore and admission checks remain work.
- The installed local AWS CLI is 2.15.31, with no profiles or credentials. Browser sign-in was subsequently verified in Firefox for the management account and Blank Slate workload account. Advanced AWS features are enabled. Browser authentication does not automatically configure CLI credentials.
- Git's local HEAD points at an old October main commit and the repository is configured bare. Cached origin/main and the November 18 feature branch include the advisor and infrastructure files. The earlier Brain claim that the app exists only on this Mac is stale. Verify the remote and build an explicit clean release checkout before configuring deployment.
- Current model-pricing review expires November 24 at 8:03 p.m. Eastern. The retained Part D review deadline is November 23 at 7 p.m. Eastern. Revalidate against actual source controls before release.

## Small deployment

Use AWS us-east-1, CloudFront with WAF, and one EC2 host with encrypted EBS and PostgreSQL for the display subset. Keep the research database in its existing environment. Use two isolated app services, invitation stores, guest namespaces and data bindings for test and pilot. A shared host limits initial cost but creates a common availability boundary.

D193 selects the Pro-compatible public-origin proposal with CloudFront-only HTTPS ingress and a distribution-specific origin token. Remove the existing NAT in reviewed stages while preserving the host and disks. Outbound usage limits, proxy authentication and origin TLS remain release prerequisites. The original private VPC-origin alternative does not fit the Pro tier.

Use ACM in us-east-1 for the viewer certificate. Inspect the authoritative DNS provider and current records, then add certificate validation and the necessary web records. Retain existing mail records. The apex requires an alias/flattening-capable DNS provider. If unavailable, plan the smallest DNS change that supports the apex after reviewing the current zone.

Keep HTTPS through the origin, private responses and errors uncached, secrets in Secrets Manager, the instance role restricted to its own resources, administration through SSM, encrypted backups and bounded content-free logging. Verify applicable AWS services and account BAA coverage and the exact OpenAI organization/project, endpoint, retention and processing-region configuration before real participant information is admitted.

D191 supersedes the earlier $75–$150 range. The presented foundation configuration has a $72.27 monthly baseline plus $30 allowance ($102.27 estimate, based on 730 hours). D193 continues the disclosed Pro replacement proposal: approximately $54.42/month baseline plus $7 origin-certificate issuance/renewal, tax and remaining usage. Disclose pricing and obtain explicit approval before any additional paid service, upgrade or cost expansion outside that scope. The $30 allowance is not blanket permission to add services. This is an estimate, not an AWS hard billing cap: month length, metered requests/storage/transfer and applicable tax can change the invoice. AWS billing alerts can lag charges. The separate $20 messaging allowance cannot cap AWS costs. [Price breakdown and remaining exposure](STEP_2_FOUNDATION.md).

## Cost and abuse controls

The initial local implementation uses the owner's suggested $2 per session and $20 cumulative online model allowance. A session is one redeemed invitation so cookie renewal and refresh cannot create another allowance. Reissuing an invitation requires operator action. The settings have no calendar reset.

Before provider submission, reserve the maximum permitted output and exact counted input cost. Include extraction, composition, repair and uncertain requests. Enforce both limits within the same SQLite write transaction. Preserve all ledger rows across release replacement and rollback. A lost response keeps its reservation until reconciled. Require current reviewed model prices and approved provider settings. Block paid messaging when accounting cannot be verified.

All online paid use must consume one authoritative $20 ledger. On the initial shared host, mount that ledger into both services and use disjoint invitation identifiers. This cross-environment deployment binding still needs verification. Moving the services to separate machines requires a shared transactional accounting service. Independent $20 ledgers would increase the total allowance.

Existing invitation checks include expiry, single redemption, revocation, guest binding, CSRF and route allowlisting. Existing participant pacing permits one in-flight request, a three-second gap and ten requests per minute. WAF adds coarse IP-based protection. Verify process-wide worker bounds, body limits, timeout behavior, token-count endpoints and all paid paths on the real hosted entry point.

At exhaustion, message submission returns a paused response and deterministic browsing remains available. Existing switches provide an immediate operator pause. The local implementation includes a $2 invitation check for expanded input reservations, which is necessary because funding output alone cannot bound a long prompt.

## Release and rollback

1. Create a clean release branch from the actual working feature baseline and apply the targeted changes. Scan the selected artifact for secrets and excluded local stores. Pin runtime and dependencies. Generate code, data, prompt/model-policy and schema identifiers.
2. Add GitHub Actions with AWS OIDC scoped to the exact repository and deployment branch or environment. Passing PR checks produce one immutable release artifact. A merge deploys that artifact automatically to the test hostname.
3. After owner inspection, promote the same artifact by an explicit release action. Private GitHub Free approval limitations must be reflected honestly in the procedure. Keep deployment approval separate from auto-merging source changes.
4. Pause new pilot admissions and wait for active visits before replacing the single process. Current chat lives in RAM, so starting a new process cannot preserve a visit automatically. Schedule updates between sessions until shared visit state is implemented.
5. Retain the previous release and provide one rollback action by artifact digest. Code rollback retains current invitation, revocation and budget state. Use backward-compatible schema changes, a migration lock and a tested backup/restore procedure for data migrations. Never restore an old spending ledger over newer charges.
6. Record the release ID on hosted responses and content-free access events. Associate observer notes and consented pilot evidence with the same release. Persistent raw transcripts require the existing consent, retention and storage work before activation.

## Demo notice and real pilot scope

The invitation page now says Demo only, describes the 2026 Collier data and asks users to use fictional details. This is the initial hosted rehearsal assumption. The real-situation pilot still requires its privacy notice, consent and accepted vendor configuration. Before that transition, revise the notice to accurately describe approved use. Avoid repeated disclaimer paragraphs in the conversation and keep the plan year visible with the results.

## Execution sequence and completion evidence

| Work | Completion evidence |
| --- | --- |
| Account access and inventory | Workload identity, region, BAA scope, existing resources and DNS ownership verified |
| Hosted runtime | Latest :8895 capabilities explicitly bound to invite-controlled production entry point, all paid stages use the same ledger |
| Data restore | Linux restore parity, reader permissions, source STOP propagation and freshness checks |
| Infrastructure and TLS | Reviewed priced change set, HTTPS, direct-origin denial, zero private cache replay |
| Release pipeline | Push reaches test, approved artifact reaches pilot, rollback restores last working code |
| Fictional verification | Two-guest isolation, expired/revoked invitations, CSRF, budget concurrency, uncertainty, burst handling, provider outage, recovery and slow requests |
| Participant readiness | Demo notice or approved real-pilot consent, redaction, data handling, owner review and applicable launch gates |

Allow roughly 2–4 focused engineering days for the remaining implementation and deployment verification once access and scope are settled. The half-day estimate in the quoted discussion assumes a deployable runtime and completed account integration, which this repository does not yet provide.

## Work completed in this review

Implemented the initial $20 aggregate and $2 invitation checks in the existing hosted rehearsal ledger, connected every existing adaptive model agent to that ledger, checked expanded input reservations, added the pre-entry demo notice and added a release digest to hosted response headers and content-free access events. Added a read-only aws-inventory.sh with an expected-account guard.

The original socket-based test run passed 35 checks and hit three sandbox socket-bind errors. After the added expanded-input regression, 39 checks passed using real HTTP handler/client codecs over in-memory transport. This verifies handler logic while actual network transport remains unverified. A 356-file private package built and imported its entry point in a clean extraction on macOS. Linux deployment remains pending. Browser rendering checks were blocked by local-file browser policy and a headless-browser failure, so desktop/tablet/phone rendering remains unverified.

No hosted release or live-provider probe has been completed. The regional policy blocker is resolved. The subsequent private foundation is created and verified, with no public application; see Step 2 for actual resource and cost evidence. Namecheap validation records have since been saved and confirmed by public DNS and ACM issuance. The Brain is readable through its synced folder, but its directory is outside this session's writable roots, so this repository document is the continuation record.

## Primary references

- [AWS login and minimum CLI version](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-sign-in.html)
- [AWS Agent Toolkit setup](https://github.com/aws/agent-toolkit-for-aws/blob/main/setup-instructions/setup.md)
- [CloudFront VPC origins](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/private-content-vpc-origins.html)
- [CloudFront certificate requirements](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/cnames-and-https-requirements.html)
- [VPC and NAT pricing](https://aws.amazon.com/vpc/pricing/)
- [AWS Budgets timing](https://docs.aws.amazon.com/cost-management/latest/userguide/budgets-managing-costs.html)
- [WAF rate-limit behavior](https://docs.aws.amazon.com/waf/latest/developerguide/waf-rule-statement-type-rate-based-caveats.html)
- [AWS HIPAA eligible services](https://aws.amazon.com/compliance/hipaa-eligible-services-reference/)
- [OpenAI API BAA](https://help.openai.com/en/articles/8660679-getting-a-business-associate-agreement-for-the-openai-api)
- [GitHub OIDC trust claims](https://docs.github.com/en/actions/reference/security/oidc)

## Verified AWS access and resolved policy blocker

The follow-up browser session reached authenticated CloudShell in both the Blank Slate workload account and the Daylight Management Account. Workload identity was verified by STS. CloudFront returned no distributions and Route 53 returned no hosted zones in the workload account. Domain DNS may be managed elsewhere. The EC2 inventory and Secrets Manager inventory in us-east-1 were explicitly denied by an organization service control policy.

Read-only inspection from the management account identified AdvancedModeRegionRestrictionSecurityControlPolicy, policy p-nh0ejrgr, attached to the organization root. Its UsEast1Partitional statement denies actions outside a service exception list when aws:RequestedRegion equals us-east-1. EC2 DescribeInstances and Secrets Manager ListSecrets are outside that list. Another statement limits us-west-2, and RegionFloor limits other regions. This explains why the browser defaults the workload account to Ohio.

The owner-approved change was applied November 18 at 4:51 p.m. Eastern: a StringNotEquals condition for aws:PrincipalAccount equal to 020055445580 was added to UsEast1Partitional. The script retained the complete original policy, checked account, organization, root attachment, metadata and content drift, and verified AWS readback. Other conditions and statements are unchanged. The subsequent workload inventory completed with exit code 0, including EC2 and Secrets Manager. [Receipt, inventory and rollback route](STEP_1_ACCOUNT.md).

The local CLI remains unconfigured, but CloudShell supplies an authenticated operational route. The local shell cannot resolve external hosts in this restricted session, so downloading or updating its CLI was unsuccessful. A browser login is now verified, and it is unnecessary to ask the owner to repeat it.


## D186 additions before deployment

The owner confirms Namecheap registration. Check the live nameservers to determine the authoritative DNS host. Namecheap BasicDNS, FreeDNS and PremiumDNS support apex ALIAS records, which can target CloudFront. Add the test subdomain and ACM validation records at the actual DNS host. Confirm existing email records during the change.

Full conversation history is now part of the hosted release target. This supersedes the visit-only target in earlier sections for the hosted pilot. The new hosted code has consented PostgreSQL history; the existing local app stays visit-only. Private database verification passed; production installation and retention/backup operations remain pending.

### History design

Store every submitted turn, delivered assistant reply, visible card or table, structured choice and correction needed to reconstruct the visit. Include timestamps, pseudonymous participant/visit and request identifiers, consent notice version, release digest, source-data version, model/prompt-policy version, charged usage and errors/status. Distinguish accepted, delivered, failed and interrupted events. Use stable event IDs and transactional writes so retries cannot duplicate turns or overwrite history. Persist accepted input before acknowledging it and persist the validated response before delivery. If saving fails, pause new turns and report the failure accurately.

Use a dedicated encrypted PostgreSQL schema on the initial host, with narrowly scoped application writes and per-participant reads. Provide founder-only review through authenticated administration with MFA and access audit. Keep browser session credentials, secrets and full model prompts out of the archive. Redact prohibited identifiers before saving or model transmission and regression-test near-miss Medicare-number and SSN cases. Save no unsent drafts. Model context should use only the visit's authorized data.

Back up encrypted history to private S3 with KMS, Block Public Access and a separate backup role. Test restoration. Prevent public object URLs and cross-participant reads, and ensure archived history cannot be served as static assets. Content-free operational logs remain separate. A durable archive does not by itself implement seamless cross-device recovery or multi-instance deploys.

D187 approves retention of 90 days from visit completion for pilot transcripts, with backup copies expiring within a further 30 days. Keep pseudonymous numeric usage under D101. Design deletion to cover database rows, derived exports, object versions and restored backups through a deletion journal. Avoid an indefinite retention or automatic legal-hold assumption. Confirm applicable legal retention separately if the product later accepts enrollment or sales activity.

Before the first saved message, explain in plain language what is saved, why, who can review it and when it is deleted, and record the participant's agreement. For a participant who declines, retain access to the deterministic educational pages. Replace the fictional-only rehearsal notice with the approved real-pilot wording when the actual data handling and vendor settings are verified.

### Key and abuse protections

Use a dedicated production project/service account and restricted API permissions. Store its key in Secrets Manager, retrieve it through the runtime instance role, and keep it outside frontend files, public responses, model context, source control, deployment artifacts and logs. Inspect the release artifact and browser traffic for leakage. Test key rotation and emergency revocation. Restrict provider destinations and model choices server-side.

The $20 transaction ledger limits calls through Daylight. A copied provider key could be used outside Daylight and bypass that ledger. Verify any provider-enforced account limit separately and configure anomaly alerts and emergency key revocation. Domain access, invitation gating and the ledger together reduce misuse through the app, while least-privilege secret access addresses key theft.

Acceptance includes secrets scanning, rendered-page and network inspection, guest isolation, archive authorization, restore/deletion, concurrent reservation checks, uncertain charges, malformed requests, cache isolation and denied direct-origin access. These are required release checks from the approved design and are not yet a hosted security assurance.


## D187 approved release configuration

Use GPT-6.1 Sol with low reasoning for both interpretation and composition. The local launcher pins gpt-6.1-sol and the development model allowlist excludes 6.2. Existing pilot routing already permits only 6.1. Existing Sol pricing and cache accounting are retained. Runtime activation must be verified after restart. Offline model tests passed six of seven checks, including both-stage low reasoning, with a failure in the Maya requested-start capture assertion. No provider calls were made.

The owner approves the reusable accelerator link proposal. Each redemption creates its own isolated visitor identity/history, while the shared link remains usable until expiry or revocation. The reusable-link extension is now implemented and offline verified; the production invitation store still needs migration and activation. Keep a link-level aggregate budget as well as the cumulative ledger, because new browsers can otherwise obtain fresh per-visit allowances.

Configure a dedicated demo OpenAI project with a $20 monthly spend limit and Enforce a hard limit enabled. Verify this in the actual provider account. This applies to direct requests using the project's key as well as app requests. Enforcement can slightly overshoot and resets monthly. Daylight's cumulative ledger remains active across months. This supersedes older statements that OpenAI project controls are alerts only. Provider settings have not yet been changed.

The earlier history retention proposal was included in the owner's general agreement. Use 90 days after visit completion and backup expiry within a further 30 days for the pilot design, with participant disclosure and deletion handling as specified above.
