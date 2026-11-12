# Vendor register (HP-03)

Draft · November 7, 2026 · Daylight security program. Owner: the security and privacy official ([HP-01](HP-01_SECURITY_PRIVACY_OFFICIAL_2026-11-07.md)). Built from the P0 rows of the [MVP requirements workbook](../Daylight_MVP_Requirements_2026-11-07.xlsx), the [AI-native brokerage plan](../AI_NATIVE_BROKERAGE_PLAN_2026-11-05.md) §5 and the [launch tools and costs report](../LAUNCH_TOOLS_AND_COSTS_2026-11-07.md). Data classes come from the [data classification policy](HP-02_DATA_CLASSIFICATION_POLICY_2026-11-07.md). Covered-service lists were checked against AWS's and Anthropic's own pages on November 7, 2026. Not legal advice.

**Rule.** No vendor touches Class 2 until its row here shows a signed contract and the specific services Daylight uses are covered by it. Re-check covered-service lists quarterly, because vendors change them.

## 1. Pilot vendors (P0)

| Vendor | Data it sees | Contract | Status |
| --- | --- | --- | --- |
| AWS | Class 2, 4, 5 within approved services | AWS Artifact BAA | D101 owner reports signed. Verify the target account and services (HP-04). |
| OpenAI GPT API | Class 2 only via verified eligible routes | OpenAI API BAA | D101 owner reports signed. Verify the exact project, endpoints, model and data controls. |
| Anthropic (Claude API) | Development fictional data only for this scope | Separate vendor record | D101 selects OpenAI for the pilot. |
| Langfuse, self-hosted | Class 4 only | None needed | Not deployed (HP-09) |
| GitHub | None allowed | None | In use; fictional data only |
| Coding agents (Claude Code, Codex, Paperclip) | None allowed | Not covered | In use; fictional data only |
| Termly | None | Standard terms | Not started (LG-05) |
| Founder email and phone | Class 3 intended | Depends on provider | Decide before invitations |
| Session observation or recording tool | Class 2 if recorded | Undecided | Decide before invitations |

### AWS

- **Use:** hosting the advisor (ECS on Fargate, or EC2), the operations and research PostgreSQL databases (RDS), secrets (Secrets Manager, KMS), DNS and TLS (Route 53, Certificate Manager), access control and audit (IAM, CloudTrail), backups (S3, AWS Backup), support email (SES), and the self-hosted Langfuse server.
- **Contract:** AWS Business Associate Addendum, accepted in AWS Artifact. If accepted as an Organization agreement from the management account, it covers every current and future account in the organization.
- **Covered services Daylight plans to use with Class 2:** all are on AWS's HIPAA-eligible list (updated July 14, 2026): ECS, Fargate (ECS engine), EC2, RDS (PostgreSQL engine), S3, Secrets Manager, KMS, CloudTrail, CloudWatch, Route 53, Certificate Manager, SES, AWS Backup, ECR and Organizations. Later: Cognito, ElastiCache, CloudFront (Embedded Points of Presence excluded), WAF, Shield and Bedrock.
- **Region:** US East (N. Virginia), `us-east-1` (D101 / IN-01).
- **Next step:** verify the target AWS account's agreement coverage and controls. The founder reports security setup is complete.
- **Sheet rows:** HP-04, IN-01, IN-02, IN-03, IN-06, IN-07, IN-11, SA-01, ES-01.

### Anthropic (Claude API)

Historical proposal. D101 selects the OpenAI GPT API for the pilot.

- **Use:** the advisor's language model, through the Messages API.
- **Contract:** Anthropic's standard BAA, enabled self-serve in the Claude Console (Data retention page). Enablement is immediate, permanent for that organization, and bound to the BAA version downloaded. Record the version and date here when accepted.
- **Covered:** Messages API, token counting, prompt caching, structured outputs and strict tools (no health information in schemas), thinking, citations, web search, and US data residency (`inference_geo`).
- **Not covered:** Batch, Files, code execution, MCP connector, web fetch, tool search, context editing, compaction, message threads and Managed Agents (the API rejects these in a HIPAA organization), and the user profiles API (allowed, but must hold no health information). Also outside the BAA: the Console playground and Claude Code.
- **Retention:** prompts and outputs are not retained by default. Covered Models (Fable, Mythos) require 30-day retention, so Daylight keeps them off health-data paths. Content flagged by Anthropic's safety systems may be kept up to two years under any arrangement.
- **Region:** US-only inference (AI-05, 1.1× token price).
- **Next step:** create a new organization for production and enable HIPAA readiness there. Keep the existing development organization on standard terms for evaluations with fictional data (AI-02). Make Claude the pilot advisor's default model (see OpenAI).
- **Sheet rows:** HP-05, AI-02, AI-04, AI-05, AI-10.

### OpenAI API

- **Use today:** the advisor's default model in development (GPT-6.1 Sol, with GPT-5.4 as baseline).
- **Contract:** founder reports a signed OpenAI API BAA under D101. Record the agreement reference and verify the applicable project, exact model, endpoints and effective data controls before participant traffic.
- **Next step:** bind the pilot runtime to the verified OpenAI project with a scoped secret and fail-closed route. Verify generation and input token counting separately. Review against the [OpenAI API data controls](https://developers.openai.com/api/docs/guides/your-data) and [HIPAA eligibility](https://help.openai.com/en/articles/20001069-hipaa-eligible-products-and-functionality).
- **Sheet rows:** AI-03, AI-04, VE-14.

### Langfuse (self-hosted, open source)

- **Use:** traces of model calls and usage metering (HP-09, SA-17, PX-11).
- **Contract:** none needed. The software runs inside Daylight's AWS account, so no data goes to Langfuse the company.
- **Next step:** run it on AWS; mask inputs and outputs in the SDK; turn off its product telemetry; confirm its own application logs do not echo trace payloads.

### GitHub

- **Use:** source code, and code-owner review of health-data paths (OP-09).
- **Data:** none allowed. The repository is planned to be public (`docs/project/storage-map.json`).
- **Next step:** keep secret scanning on, ignore any export folders, and never commit transcripts, notes or participant lists.

### Coding agents (Claude Code, Codex, Paperclip on the laptop)

- **Use:** building Daylight (OP-07).
- **Data:** none allowed. Anthropic states Claude Code is not covered by HIPAA readiness; Codex and Paperclip have no BAA.
- **Next step:** agents work from fictional personas only. Real transcripts and participant details never enter their context, including pasted excerpts.

### Termly

- **Use:** first draft of the privacy notice and terms (LG-05).
- **Data:** none; policy text only.
- **Next step:** publish the generated text as static text on Daylight's own pages. Do not embed Termly's scripts or cookie banner on pages that show health information (spec §6.5).

### Founder email and phone

- **Use:** club introductions, scheduling and follow-up (MV-04), and `support@` (ES-01).
- **Data:** Class 3 intended. The risk is participants replying with health details.
- **Contract:** depends on the provider. Consumer email and phone carriers: none. Google Workspace offers a BAA for its paid editions (confirm the edition). Paubox signs a BAA on every plan. SES is covered by the AWS BAA.
- **Next step:** use email only for scheduling, with a line asking people not to send health details, and route anything health-related to in-app messages (ES-01). If `support@` will receive health details, put it on a BAA-covered mailbox.

### Session observation or recording tool

- **Use:** watching at least eight live sessions (MV-07) and any recorded interviews (MV-06).
- **Data:** Class 2 if recorded; screens and voices show health details.
- **Next step:** choose before invitations, because the consent step depends on it (HP-13). Either take minimized written notes with no recording, stored under the participant code on AWS, or use a recording tool under a BAA. If audio is recorded, get every party's consent (MV-06 note on Florida's recording law).

### Stores that are not vendors

- **Pilot invite list** (MV-03): Class 3 plus the participant-code key. Keep it in the operations database or one encrypted file, never in a shared sheet with notes about anyone's health.
- **Founder's laptop:** no Class 2 at rest (HP-02 §4).

## 2. Vendors planned for later

None of these may receive Class 2 until moved into section 1 with a signed contract.

| Vendor | Planned use | Would see | Needed before use | Sheet rows |
| --- | --- | --- | --- | --- |
| Amazon Bedrock | Second model path; cross-family grounding judge | Class 2 | AWS BAA (Bedrock is eligible; Anthropic's BAA does not cover it). Keep invocation logs inside the BAA account or off. | AI-06, VE-14 |
| Amazon Cognito | Passwordless sign-in at checkout | Class 3 linked to Class 2 | AWS BAA | IN-15, SA-19 |
| Amazon ElastiCache | Allowances and pacing | Class 4 (opaque IDs) | AWS BAA; key on opaque IDs | SA-05 |
| CloudFront, AWS WAF, Shield | Edge gate before public traffic | Class 2 in transit | AWS BAA; CloudFront Embedded Points of Presence excluded | SA-03 |
| Cloudflare Turnstile | Invisible bot check | Browser signals, no chat content | Cite its privacy addendum in the privacy notice | SA-04 |
| Sentry | Error tracking | Class 2 risk in error payloads | BAA on the Business plan; scrub health data; Session Replay off | IN-04, HP-06 |
| Paubox or SES | Transactional email | Class 2 possible | BAA (Paubox on every plan; SES under AWS) | IN-13, HP-06 |
| Twilio Verify | Checkout codes | Class 3 | BAA only on Security or Enterprise Edition (quote needed); health-free messages | IN-14, SA-19 |
| CSG Actuarial | Medigap rates, drug pricing | Class 2 if quoted per person | Ask about a BAA; cache by rate cell, not by person | DQ-03, DQ-21 |
| NLM RxNav, NPPES API, carrier FHIR directories | Drug normalization, NPI lookups, network checks | Class 2 if queried live for a person | Prefer local copies; register any live per-person lookup | DQ-13, DQ-16, DQ-20 |
| FMO (Spark, Benefits Life or Ritter) and its quoting and enrollment tools | Contracting, quoting, enrollment | Class 1 and 2 | BAA; one-to-one TPMO consent per named recipient (spec §5.2.11) | CL-10, ES-03, ES-15 |
| Enrollment platform (SunFire, Convey, CSG) | Enrollment | Class 1 and 2 | BAA; TPMO consent | ES-04 |
| Agency CRM (MedicarePro, AgencyBloc) | Book of business | Class 1, 2 and 6 | BAA; TPMO question for counsel | ES-06 |
| Recorded phone line (Recordia, IntegrityCONNECT) | Recorded calls | Class 2 | BAA | ES-10 |
| TrustedForm | Consent certificates | Class 3 | Terms; its 5-year retention is shorter than record retention, so export and archive | HP-20 |
| Dagster, dbt (open source, on AWS) | Public data pipelines | Class 5 only | None; keep out of operations data | Plan §5 |
| promptfoo, Braintrust | Evaluation harness | Fictional data only | None while fictional; hosted Braintrust never receives real data | Plan §5 |
| Front or Zendesk, Vanta or Drata, research panels, Origami or Apollo, Google Ads | Support, compliance, recruiting, partner outreach, ads | Varies | Classify before use; no ad pixels on health pages | Plan §5, GTM |

## 3. Open items

1. Accept the AWS and Anthropic BAAs and record the date and version for each (HP-04, HP-05).
2. Confirm the founder's email provider and whether a BAA is in place.
3. Choose the session-observation method before invitations.
4. Confirm the advisor's default model is switched to Claude before the first real participant.
