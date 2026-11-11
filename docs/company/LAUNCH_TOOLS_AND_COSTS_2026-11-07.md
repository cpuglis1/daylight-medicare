# Daylight launch tools, costs and decisions

Research and decision guide · November 7, 2026 · Read with the [AI-native brokerage plan](AI_NATIVE_BROKERAGE_PLAN_2026-11-05.md) and the [launch security spec](LAUNCH_SECURITY_SPEC_2026-11-06.md). This maps options, tools and costs and recommends decisions. It records no new numbered requirement and approves nothing by itself. It is not legal advice.

**Bottom line: launch lean, start hybrid, prove one channel.** Daylight can launch its Collier County MVP on a bootstrap budget. On the lean path that is **about $14k–$27k one-time and $850–$2,450 a month off-season, rising to roughly $1,300–$5,500 a month during the Annual Enrollment Period (AEP)** (est.). Every hard part the founder named has a cheap, compliant option:

- **Health data.** Frontier models can process health data under self-serve business associate agreements (BAAs) at list price.
- **Bots and spend.** Bot and cost protection runs on the cloud provider's own edge for tens of dollars a month.
- **Security program.** The written program can start from a free HHS tool.

The fully managed version of the same stack costs about three times as much one-time ($39k–$81k) and about eight to ten times as much each month (est.). Most of the monthly gap comes from three lines: Cloudflare Enterprise, a fractional general counsel and paid licensed review.

The real limits are timing, licensing and revenue, not tools:

- **Timing.** The AEP now under way is out of reach. The realistic first legal enrollment falls between mid-December 2026 and January 2027.
- **Revenue.** A neutral recommender earns **about $240 per AEP conversation in year one** under 2027 Florida commission schedules (illustrative). Plan switchers pay the $363 renewal rate, many PPOs pay $406 or less, and standalone Part D pays $0.
- **Contracting.** Going direct to carriers on day one buys control and book ownership but not more money per enrollment. The recommended path is a hybrid: start under an agency-friendly FMO with agency-owned contracts and an open release, then move direct one carrier at a time once Daylight has production data.

Three other conclusions:

- **Paperclip** is real but young, and has had a CVSS 10.0 vulnerability. It belongs on internal work that touches no health data.
- **Validation.** The evidence supports using AI to screen recommendations, not to certify them. That makes Option B licensed review plus the deterministic engine the right launch design.
- **Go-to-market.** The one channel to prove first is turning-65 direct mail in Collier County.

This is research, not legal advice. Every item marked for counsel needs a lawyer's decision.

*How to read this report.* A figure with a link is sourced; the date is the source's. **(est.)** marks an estimate, and the text says whether it is the researchers' or mine. **Confirm** marks a point where sources conflict or a fact could not be verified. Founder context (the "buy the rails, build the brain" plan, Option B, the launch security spec and its open decisions D1–D6) comes from Daylight's own documents, not from research. I checked the Anthropic API figures against Anthropic's official pages on November 7, 2026: prices, US-only routing, HIPAA readiness and spend tiers.

## Economics: going direct buys control, not more commission

**Bottom line:** at pilot scale, an FMO does not reduce Daylight's commission, and going direct does not raise it. Either way Daylight earns the carrier's street-level rate. Money above street level (overrides, administrative and marketing payments) goes to whoever holds top-of-hierarchy status, and a new agency without production history is unlikely to get that.

The real choice is about control, speed and services. I recommend a hybrid. Contract through a tech-neutral FMO that gives Daylight agency-owned carrier contracts, immediate vesting, an open release and no assignment of commissions. Then pursue direct or top-of-hierarchy contracts one carrier at a time once Daylight has retention and complaint data. This departs from the founder's leaning toward going fully direct now, for the reasons below.

### What carriers will pay in 2027

For plan year 2027, CMS's maximum ("fair market value") compensation for Florida, which sits in the "all other states" tier, is:

| | 2027 initial | 2027 renewal | 2026 initial | 2026 renewal |
|---|---|---|---|---|
| Medicare Advantage | $725 | $363 | $694 | $347 |
| Standalone Part D | $130 | $65 | $114 | $57 |

Sources: [Ritter/Medicareful, June 3, 2026](https://medicareful.ritterim.com/blog/2027-maximum-broker-commissions-for-medicare-advantage-and-medicare-part-d); [CMS CY2027 memo](https://advocacy.naifa.org/hubfs/CMS%20memo.6.5.pdf).

Renewals are capped at 50% of the initial amount. Referral fees stay capped at $100 per MA and $25 per PDP enrollment ([CMS CY2027 memo](https://advocacy.naifa.org/hubfs/CMS%20memo.6.5.pdf)).

The CY2025 rule tried two things: fold administrative payments into one fixed rate, and ban contract terms that inhibit objective recommendations. Both were vacated on August 18, 2025 in *Americans for Beneficiary Choice v. HHS*. The government did not appeal, and CMS now applies the pre-2025 regulatory text "until further notice" ([court opinion](https://www.mintz.com/sites/default/files/media/documents/2026-01-06/CMS-ruling-N.D.-Tex.pdf); [CMS CY2027 memo](https://advocacy.naifa.org/hubfs/CMS%20memo.6.5.pdf)).

The same court upheld the rule that a TPMO may not share a beneficiary's data with another TPMO without prior express written consent. That rule still governs Daylight's leads and partner hand-offs.

Because of the vacatur, carriers can again pay FMOs and agencies administrative and marketing money outside the cap, which is why hierarchy position matters. One caution: a DOJ False Claims Act case alleges that large MA plans paid brokers disguised "marketing" fees to get around the caps. A motion to dismiss was pending in February 2026 ([Morgan Lewis, Feb 6, 2026](https://www.morganlewis.com/fr/blogs/healthlawscan/2026/02/medicare-advantage-agent-and-broker-agreements-2025-in-review)). **Confirm** its current status.

The cap is a ceiling, and Florida carriers pay less on a growing share of plans:

- **UnitedHealthcare.** The 2027 Florida schedule pays $725 on SNPs and $700 on non-SNP HMOs, but **only $406 on non-SNP PPOs and $0 on PDP**. Renewals are $350 for HMOs and $203–$313 for PPOs. Two Florida AARP regional PPOs pay nothing ([UHC 2027 amendment](https://irp.cdn-website.com/813754df/files/uploaded/Agent+2027+Annual+Commission+Amendment.pdf)).
- **Humana.** Pays the full $725 / $363 on commissionable MA, but **$0 on new PDP and on seven named all-county Florida PPOs** ([Humana 2027 PPP](https://assets.humana.com/is/content/humana/Humana%20Individual%20Products%20PPPpdf)).
- **Aetna.** Made 123 MA plans in 33 states non-commissionable for 2027. The state list was not published ([Medical Daily, Aug 19, 2026](https://www.medicaldaily.com/aetna-medicare-advantage-broker-commission-freeze-2027-477523)).

Florida's 2027 market is also churning. Plan offerings fell from 611 to 560, and about 17% of Florida general-enrollment members are in plans not offered for 2027 ([InsuranceNewsNet, Oct 15, 2026](https://insurancenewsnet.com/oarticle/florida-is-losing-more-medicare-advantage-plans-in-2027-than-any-other-state); [Oliver Wyman, Nov 4, 2026](https://www.oliverwyman.com/our-expertise/perspectives/health/2026/nov/medicare-advantage-market-2027-plan-exits-snp-growth.html)).

Medigap is the exception to shrinking pay. Commissions are a carrier-set percentage of premium with no CMS cap:

- At Humana, about 22% of premium in years one to six (26% for Plan N), then 2.5% ([Humana 2027 PPP](https://assets.humana.com/is/content/humana/Humana%20Individual%20Products%20PPPpdf)).
- Florida rule 69O-156.013 limits first-year pay to 200% of the second year and requires level renewals for at least five years ([FAC 69O-156.013](https://state-rules.com/florida/fac/69O-156.013/)).
- eHealth's lifetime commission value per approved member in Q4 2025 was **$1,496 for Medigap against $1,304 for MA** ([eHealth FY2025 results](https://mma.prnewswire.com/media/2920363/eHealth_2025_Results.pdf?p=original)).
- Guaranteed-issue, under-65, age-80-plus and internal-replacement Medigap sales pay far less.

The only Florida-adjacent Medigap schedules found were Humana's carrier-wide tables and an Arizona-oriented general agency sheet. **Confirm** Florida rates with each carrier.

### FMO versus direct, side by side

| Dimension | Through an FMO | Direct to carriers as a new agency | What to negotiate or note |
|---|---|---|---|
| Commission per enrollment | Street level, paid by the carrier ([Integrity](https://integrity.com/insights/comparing-fmos-that-specialize-in-medicare-products/)) | Street level | Same either way at pilot scale |
| Overrides, admin and marketing money | Kept by the FMO. MA plans paid FMOs about $200–$300 per beneficiary in 2024 ([InsuranceNewsNet, Apr 8, 2024](https://insurancenewsnet.com/innarticle/proposed-medicare-advantage-regulations-would-impact-broker-fmo-compensation)) | Only with top-of-hierarchy status; no published production bar | Current override levels are unpublished |
| Contracting speed | One workflow into 100+ carriers (Ritter "Contract Now", 120+) ([Ritter](https://ritterim.com/blog/ready-to-join-an-fmo-10-things-to-consider/)) | Each carrier separately; "several days or several weeks" ([Empower Brokerage](https://www.empowerbrokerage.com/?p=100167)) | Contracting slows near AEP |
| Book ownership and renewals | Depends on contract. "Assignment of commissions" lets the upline keep renewals if you leave ([Ritter](https://ritterim.com/blog/ready-to-join-an-fmo-10-things-to-consider/)) | Agency owns the book | Insist on agency-owned contracts and no assignment |
| Leaving | Ritter: no releases Sept 1–Dec 31 and a six-month delay for new agents. Without a release, a 90-day intent-to-move wait ([Spark release guide](https://help.sparkadvisors.com/en/articles/14356612-release-requests-a-detailed-guide-to-the-process)) | Not applicable | Open release with no blackout. Benefits Life offers open release and day-one vesting ([Benefits Life](https://benefitslife.com/fmo-for-medicare-agencies.html)) |
| Technology | Free quoting, CRM and e-apps (Sunfire, IntegrityCONNECT) | Build your own, or license platforms | Daylight builds its own, so FMO tech is only a pilot bridge |
| Commission reconciliation | Spark automates reconciliation and recovers unpaid commissions ([Spark](https://www.sparkadvisors.com/call-center-operators)) | Daylight builds it | Automatable by Daylight |
| Plan commission-status feeds | FMOs aggregate carriers' mid-season $0 notices | Daylight tracks each carrier | Automatable by Daylight |
| Compliance and AHIP | Free guidance; AHIP for $125 instead of $175 | Carrier links also discount AHIP ([Spark](https://help.sparkadvisors.com/en/articles/15118113-ahip-2027)) | Minor |

Spark says agents keep 100% book ownership, that it is paid on the override side, and that it "often earns more revenues when agencies contract directly." That suggests a tech-first FMO will accept the hybrid ([IHA on Spark](https://independenthealthagents.com/platforms/spark/); [Spark FAQ](https://sparkadvisors.com/faqs)).

Agency-level appointments are open to a new licensed agency. UHC asks for:

- an agency license;
- at least one appointed writing agent per state;
- a signed agreement and an appointment form;
- about a week for background checks.

([UHC contract guide](https://www.wordandbrown.com/getmedia/aa6116eb-d609-48b1-a732-c8fa8bc58be1/UHC-Contract-Guide.pdf))

But many carriers prefer to work through FMOs, and carriers are pruning brokers on quality ([eHealth Q4 FY2025 slides](https://s204.q4cdn.com/837903328/files/doc_financials/2025/q4/Q4-FY-2025-Earnings-Slides-vFinal.pdf)). Going direct gets Daylight its own book and street commission, which a well-negotiated FMO contract also provides. It gets nothing extra until Daylight has data to bargain with.

The founder's goal of automating FMO functions can start now with the ones that are data and software:

- the plan-level commission-status table;
- statement reconciliation and chargeback detection;
- license and appointment tracking;
- the marketing pre-screen and filing log.

The commercial functions (hierarchy status, carrier-funded co-op money and escalation leverage) cannot be automated; they have to be earned. Time any move out of an FMO for the first or second quarter of the year to avoid release blackouts.

### What neutrality means for revenue per conversation

Payment mechanics make AEP switchers worth less than new enrollees:

- Humana and UHC pay the initial rate only when CMS flags an enrollment as new to Medicare. A like-plan switch in year two or later earns the prorated renewal rate ([Humana 2027 PPP](https://assets.humana.com/is/content/humana/Humana%20Individual%20Products%20PPPpdf); [UHC 2027 amendment](https://irp.cdn-website.com/813754df/files/uploaded/Agent+2027+Annual+Commission+Amendment.pdf)).
- Disenrollment within three months claws back the full commission. Later disenrollment is charged back pro rata.

The research team built an illustrative mix for 100 Collier County AEP conversations from the 2027 Humana and UHC schedules. It is not a forecast:

| Outcome (illustrative) | Count | Rate | Year-one revenue |
|---|---|---|---|
| New-to-Medicare HMO or SNP enrollment | 15 | $725 | $10,875 |
| Year-two-plus like-plan MA switchers | 30 | $363 | $10,890 |
| PPO switchers into a UHC PPO | 10 | $203 | $2,030 |
| Best plan is a $0-commission plan | 10 | $0 | $0 |
| PDP only | 10 | $0 | $0 |
| Keeps current plan, no agent-of-record change | 25 | $0 | $0 |
| **Total** | 100 | | **$23,795, about $240 per conversation** before chargebacks (est.) |

Medigap moves this figure most. At an illustrative Collier County Plan G premium of $2,000–$2,500 a year and 22% commission, each sale earns about $440–$550 a year for six years (researcher estimate). By my arithmetic, every ten of those per hundred conversations adds roughly $44–$55 of year-one revenue per conversation, plus a longer tail than MA. Retained MA members renew at about $363 a year while Daylight stays agent of record.

For scale, eHealth spent **$598 to acquire each MA-equivalent member in the AEP quarter** of 2025 and **$1,489 off-season** ([eHealth FY2025 results](https://mma.prnewswire.com/media/2920363/eHealth_2025_Results.pdf?p=original); [Panabee](https://www.panabee.com/news/ehealth-earnings-q2-2025-report)). A self-serve model has to acquire and serve customers far below call-center cost.

Three product rules follow:

1. **Keep a commission-status table on the fulfillment side, never in model context.** Carriers change $0 lists per plan and mid-season (Aetna on September 15; Humana "by email"), so the table needs continuous refreshes. It stays behind the existing `dl_fulfillment` boundary and the A07 canaries.
2. **Never filter or demote a plan because it pays nothing.** Agents must not omit $0-commission plans or call them unavailable ([TMS Brokerage, Oct 30, 2026](https://tmsbrokerage.com/2026/10/30/non-commissionable-medicare-advantage-plans-in-2027-what-independent-agents-should-do-when-the-right-plan-pays-zero/)). Washington's insurance commissioner tied $0-commission suppression to CMS's objective-recommendation rule ([WA OIC letter](https://www.insurance.wa.gov/sites/default/files/2025-12/2025-kuderer-letter-to-wellcare.pdf)).
3. **Make the commission-swap counterfactual test a release gate and a published trust signal.** It is the evidence that neutrality holds.

## Health data: frontier models are available under a BAA at list price

**Bottom line:** yes, Daylight can get frontier-model quality with HIPAA-level protection, with no stated minimum spend. The framing is not "getting around" HIPAA. It is staying inside it: a BAA with every vendor that touches health data, only the features each BAA covers, minimum-necessary prompts, and content-free logs.

Daylight should buy the regulated layer: model access, hosting, database, email and SMS under BAAs. It should build the thin, policy-critical glue: a fail-closed provider router, PHI-free logging and identifier tokenization. It should not buy privacy vaults or hosted AI gateways at pilot scale.

### Five paths to frontier models with health data

| Path | How the BAA is obtained | Notable exclusions and retention | Price notes |
|---|---|---|---|
| Anthropic Claude API, HIPAA-ready org | Self-serve in the Console for most orgs with Anthropic's standard BAA. Takes effect immediately and is permanent. Negotiated BAAs go through sales ([Anthropic](https://platform.claude.com/docs/en/manage-claude/api-and-data-retention)) | Not eligible: Batch, Files, code execution, MCP connector, web fetch, Managed Agents and beta features (the API rejects them with an error). Covered Models (Fable 5/5.1, Mythos 5/5.1) require 30-day retention. Flagged content may be kept up to 2 years ([Anthropic](https://platform.claude.com/docs/en/manage-claude/api-and-data-retention)) | Per million tokens, input/output: Opus 5.5 $4/$20, Sonnet 5.5 $2/$10, Haiku 5.5 $0.10/$0.50. US-only routing costs 1.1x ([Anthropic pricing](https://platform.claude.com/docs/en/about-claude/pricing)) |
| AWS Bedrock | AWS BAA self-serve through AWS Artifact at no extra cost ([Aptible](https://aptible.com/hipaa-compliant-ai-tools/aws-bedrock-baa)) | Anthropic's HIPAA readiness does not cover Bedrock; AWS's BAA does. Invocation logs contain PHI when enabled. Cross-region inference can process PHI in other regions | Claude at Anthropic list prices; regional endpoints +10%. GPT-5.5/5.4 available ([Healthcare Blocks](https://www.healthcareblocks.com/news-and-stories/frontier-ai-for-healthcare-without-leaving-your-compliance-boundary)) |
| Google Gemini Enterprise Agent Platform (Vertex) | Self-serve in the Cloud Console ([Aptible](https://aptible.com/hipaa-compliant-ai-tools/gemini-baa)) | No pre-GA models with PHI. Gemini 3.1 Pro is labeled Preview. AI Studio is not covered ([Google HIPAA](https://docs.cloud.google.com/docs/security/compliance/hipaa)) | Gemini 3.8 Flash price doubles on Jan 1, 2027 ([Vertex pricing](https://cloud.google.com/vertex-ai/generative-ai/pricing?authuser=0)) |
| OpenAI API | Apply by email. Requires "Modified Retention" in a form OpenAI chooses. OpenAI can revoke it after safety-classifier violations ([OpenAI HIPAA guide](https://cdn.openai.com/osa/baa-hipaa-guide.pdf)) | Live web search not eligible ([Aptible](https://aptible.com/hipaa-compliant-ai-tools/openai-baa)) | Third-party tracker prices only ([Morph](https://morphllm.com/openai-api-pricing)) |
| Azure Foundry | Automatic through Microsoft's data protection terms on EA, MCA or CSP subscriptions ([Microsoft Q&A](https://learn.microsoft.com/en-us/answers/questions/5824024/baa-for-azure-foundry-models)) | Default abuse monitoring keeps a 30-day store inside the BAA | Standard rates |

Two Anthropic details matter for Daylight's "no raw transcripts" stance:

- **Prefer non-Covered Models on health-data paths.** The Covered Models (Fable and Mythos) force 30-day provider-side retention. Opus 5.5, Sonnet 5.5 and Haiku 5.5 do not. Under any arrangement, flagged content may be kept up to two years. "Ephemeral" can be guaranteed inside Daylight's systems but not absolutely at the provider.
- **Keep a separate org for synthetic evals.** HIPAA enablement is permanent per org and blocks Batch. Running evaluation work on synthetic personas in a separate non-HIPAA org keeps the cheaper Batch pricing available there.

A secondary source says Anthropic's BAA is sales-assisted and takes weeks ([Aptible](https://aptible.com/hipaa-compliant-ai-tools/claude-baa)). Anthropic's own page describes self-serve enablement for "most organizations." The official page wins, but eligibility criteria are not published. **Confirm** on Daylight's account.

Whether HIPAA applies before checkout is a counsel question (spec Q1). The spec's position is to protect all health information to the HIPAA standard from the first message, and the research supports it: the cost of doing so is small.

### Where the founder's planned vendors stand

| Vendor or category | BAA status found | Implication for Daylight |
|---|---|---|
| AWS or Google Cloud | Free, self-serve | Supports D1 either way |
| Langfuse, self-hosted | No Langfuse BAA needed; Daylight implements the safeguards ([Langfuse](https://langfuse.com/baa)) | Fits the plan. Must run on BAA-covered infrastructure, and its own logs must not echo trace payloads |
| Postmark | "Will not sign any Business Associate Agreement" ([BAA Atlas](https://baa-atlas.vercel.app/vendors/postmark)) | Only for emails with no health information, such as bare sign-in links, if counsel agrees. Otherwise use AWS SES under the AWS BAA, or Paubox (BAA on every plan, free to 300 emails a month, Pro $104/month billed annually) ([Paubox](https://www.paubox.com/pricing)) |
| Twilio | BAA only on Security or Enterprise Edition, sold through sales, price unpublished ([Twilio](https://static0.twilio.com/docs/iam/twilio-editions/hippa)) | Get a quote before checkout SMS. Messages that carry no health information (a code or a link) reduce exposure |
| Passwordless auth | Clerk and Auth0 BAAs are Enterprise-only ([Clerk](https://clerk.com/security)) | Use Cognito under the AWS BAA, or build the magic-link flow on the BAA cloud |
| Database | Neon offers HIPAA on Scale at no added cost for now, with a 15% surcharge announced ([Neon](https://neon.com/faqs/best-backend-healthcare-hipaa-soc2-startup)). Supabase is about $950/month with HIPAA ([Gautam Khorana](https://gautamkhorana.com/blog/hipaa-compliant-supabase-vercel-2026/)). RDS is covered under the AWS BAA | RDS or Neon |
| Error tracking | Sentry BAA self-serve on Business or above ([BAA Atlas](https://baa-atlas.vercel.app/vendors/sentry)) | Scrub PHI; disable Session Replay |
| Metrics | No BAA found for Grafana Cloud below Enterprise ([Grafana](https://grafana.com/pricing/?pg=pricing)) | Content-free counters only |
| AgencyBloc, SunFire, Convey, CSG | Not researched | **Confirm** BAA terms. Also ask counsel whether each counts as a TPMO needing one-to-one consent (spec Q5) |

### Build versus buy

| Buy | Build | Defer |
|---|---|---|
| Anthropic HIPAA-ready org as primary; Bedrock under the AWS BAA as the second allowlisted path; BAA-covered hosting, database, email and SMS | A router with a static allowlist keyed by provider, model, endpoint, region and org. It allows no fallback outside the list and degrades to human handoff on error. It blocks non-eligible features in code and caches no responses outside the BAA boundary | Commercial privacy vaults (Skyflow and Protecto are quote-priced) ([Protecto](https://protecto.ai/skyflow-alternative)) |
| | Medicare-number tokenization: the model never needs the raw identifier | Hosted gateways. Cloudflare's BAA is Enterprise-only and Portkey is custom-priced ([Portkey](https://portkey.ai/docs/enterprise/pricing)). Aptible's gateway is $200/month plus tokens ([Aptible](https://www.aptible.com/pricing-plans/)) |
| | Langfuse SDK masking, PHI-free structured logs, and a quarterly re-check of each provider's eligibility table | Enterprise auth tiers |

One researcher suggested the open-source LiteLLM proxy for budgets and fail-closed limits. Another flagged a reported April 2026 supply-chain attack on LiteLLM; details were not verified ([DEV](https://dev.to/alejandro46/best-ai-gateways-for-healthcare-and-hipaa-workloads-5a44)). With two providers, the allowlist and budgets are a few hundred lines in Daylight's own router (researcher estimate). That is simpler than auditing a third-party dependency tree.

Self-hosting open-weight models would not remove the need for a cloud BAA and would give up frontier quality. My judgment is that it is the wrong trade for Daylight.

The two token estimates in the research differ about tenfold. One researcher put a Sonnet 5.5 conversation at about $0.09, assuming 30,000 input and 3,000 output tokens without caching. The other put a 30-turn, 60-call conversation with context growing to 110,000 tokens at **about $1.05 cached and $8 uncached**. My check against the verified prices confirms the cached figure: 3.7M cache reads at $0.10 plus 150K cache writes at $2.50 plus 30K output at $10 per million tokens. Decision D4 should rest on the persona runner's measured number, not on either estimate.

## Abuse and site security cost tens of dollars a month on the cloud's own edge

**Bottom line:** every control in the launch security spec can be bought or built for well under $200 a month at pilot traffic, plus one-time assurance work:

- a pen test at about $3k–$7k;
- an in-house LLM red-team for the cost of API calls.

The one expensive option in the spec is Cloudflare Enterprise with a BAA, estimated by third parties at $3,000–$8,500 a month. The research makes D2 an easy call: use the cloud's own edge with standalone Turnstile.

| Spec control | Tool | Cost | Status |
|---|---|---|---|
| §3.1 Edge gate (D2) | CloudFront + AWS WAF ($5 per web ACL, $1 per rule, $0.60 per million requests), with Bot Control. Common tier: first 10M requests free. Targeted tier scoped to chat endpoints: first 1M requests free, then $10 per million ([AWS WAF pricing](https://aws.amazon.com/waf/pricing)) | About $35/month at 3M requests, under $80 at 5M chat calls (researcher arithmetic). AWS's own example: targeted Bot Control on 5% of traffic costs $34/month ([AWS guide](https://aws.github.io/aws-security-services-best-practices/guides/waf/waf-cost/docs/)) | **Confirm** that WAF and CloudFront are on AWS's HIPAA-eligible list. Excludes CloudFront data transfer |
| §3.1 alternative | Cloudflare Enterprise (BAA "only with Enterprise customers") ([BAA Atlas](https://baa-atlas.vercel.app/vendors/cloudflare)) | Typically $3,000+/month ([Cloudways](https://www.cloudways.com/blog/cloudflare-enterprise-pricing/)); Bot Management bundles about $8,500/month (competitor-compiled) ([Prosopo](https://prosopo.io/compare/enterprise-bot-protection-pricing/)) (est.) | Not justified for a pilot |
| §3.2 Invisible challenge | Cloudflare Turnstile Free: unlimited challenges; works "without sending traffic through Cloudflare"; does not read form inputs ([Turnstile plans](https://developers.cloudflare.com/turnstile/plans/); [Turnstile docs](https://developers.cloudflare.com/turnstile/llms-full.txt)) | $0 | Invisible mode requires citing Turnstile's privacy addendum in the privacy policy |
| §3.2 Signed session tokens | Build | $0 | — |
| §3.3–3.4 Allowance and pacing | Redis token bucket. Upstash free tier is 500K commands/month, but its HIPAA support is Enterprise-only ([Upstash](https://upstash.com/pricing/redis.md)) | $0–$10/month | Key counters on opaque session IDs, or run Redis inside the BAA cloud (**confirm** ElastiCache eligibility) |
| §3.7 Provider spend limits | Anthropic org and workspace spend limits. A customer-set limit returns an error; hitting the tier cap pauses usage until the 1st of the next month. No limits on the default workspace ([Anthropic rate limits](https://platform.claude.com/docs/en/api/rate-limits)) | $0 | Tier caps are $500 (Start), $1,000 (Build) and $200,000 (Scale) a month. Plan the tier upgrade before AEP |
| §3.7 Kill switches | Daylight's own feature flags | $0 | OpenAI hard limits can overshoot slightly ([OpenAI](https://developers.openai.com/api/docs/guides/spend-limits.md)). Cloud billing alerts lag, so they cannot serve as kill switches |
| §3.8 Scope classifier | Haiku 5.5 on the BAA org; Bedrock Guardrails denied topics ($0.15 per 1,000 text units, third-party citing AWS) ([Cipher Projects](https://www.cipherprojects.com/blog/posts/bedrock-guardrails-production-guide-2026/)); or self-hosted Llama Prompt Guard 2 (86M model: 97.5% recall at 1% false positives) ([Hugging Face](https://huggingface.co/meta-llama/Llama-Prompt-Guard-2-22M)) | Under $5/month at pilot volume (est.) | Must be BAA-covered (spec §5.2.4). Lakera's free tier stores data in the EU, so it is unsuitable ([eesel](https://www.eesel.ai/blog/lakera-pricing)) |
| §3.9 SMS at checkout | Twilio Verify: $0.05 per successful verification plus about $0.0083 per US text. Fraud Guard included ([Twilio Verify](https://www.twilio.com/en-us/verify); [Authgear](https://www.authgear.com/post/twilio-verify-pricing-and-alternatives)) | About $58 per 1,000 checkouts (researcher arithmetic) | Restrict Geo Permissions to the US. The BAA needs Security Edition (price unknown) |
| §5.2.7 No third-party trackers | Self-hosted first-party analytics; Grafana Cloud Free for content-free metrics ([Grafana](https://grafana.com/pricing/?pg=pricing)) | $0 | — |
| §7 Pen test | Published-price vendors: $3,000–$9,000 for one web app ([Stingrai index](https://www.stingrai.io/blog/penetration-testing-price-index-2026)) | $3k–$7k one-time | Tests under $4K "are usually just automated scans" ([DeepStrike](https://deepstrike.io/blogs/penetration-testing-cost)). Require manual testing of session tokens, allowances and kill switches |
| §7 LLM red-team | promptfoo plus garak in CI (open source); optional external AI test at £6,000–£12,000 ([Stingrai](https://www.stingrai.io/blog/penetration-testing-price-index-2026)) | API costs, tens to low hundreds of dollars (est.) | promptfoo is now owned by OpenAI ([Security Boulevard](https://securityboulevard.com/2026/03/openai-acquires-security-startup-promptfoo-to-fortify-ai-agents)). PyRIT is reported both as archived and as active (**confirm**). Pin versions |
| §7 Written security program | HHS SRA Tool v3.6 (free download) ([HealthIT.gov](https://www.healthit.gov/resource/security-risk-assessment-sra-tool)) plus open-source policy templates | $0 | One document set for 69O-128.032 and the HIPAA risk analysis |
| §7 Cyber insurance | Standalone $1M policy | About $2k–$6k a year, up to about $10k if treated as PHI-heavy (researcher estimate from broker data) ([Vouch](https://www.vouch.us/blog/startup-insurance-costs); [Secureframe](https://secureframe.com/blog/cyber-insurance-costs.md)) | Agents' E&O usually excludes cyber or gives a small shared sublimit ([Rough Notes](https://roughnotes.com/agents-eo/)) |
| Gate 3 SOC 2 | Vanta, Drata, Sprinto or Thoropass plus a lean Type 1 audit | About $10k–$25k in the first year (researcher estimate) ([Klaay](https://www.klaay.com/blog/best-soc-2-tools-for-startups-2026); [SOC2Auditors](https://soc2auditors.org/soc-2-audit-cost/)) | Defer until a carrier or partner asks |

The provider spend tiers are a trap for a new account. A lean AEP model budget of up to about $3,000 a month (est., below) is above the Build tier's $1,000 cap, and hitting a tier cap stops all usage until the first of the next month. Either reach the Scale tier before the next AEP or route overflow through Bedrock. The research did not cover how an Anthropic org moves between tiers or what Bedrock's quotas are. **Confirm** both.

The spec's separate budget pools (anonymous, saved profile, checkout) map naturally onto separate Anthropic workspaces, each with its own limit. Abuse of free chat then cannot exhaust checkout.

Classifiers are a weak layer on their own: Meta's model card warns that "adaptive attacks may evade detection." The spec's structural controls matter more: no actions from anonymous chat, software-enforced scope, and model output treated as untrusted.

## Legal: narrow specialist opinions, part-paid in equity, beat one big firm

**Bottom line:** AI tools and templates can cut counsel hours by turning Daylight's questions into precise, regulation-mapped memos before a lawyer sees them. They cannot answer those questions. The cheapest credible counsel set is:

- a Florida insurance-regulatory boutique;
- a fixed-scope opinion from a national Medicare marketing specialist;
- commodity corporate work done through a formation service or a law-school clinic.

A plausible first-year legal budget is $15k–$50k (researcher estimate). Equity can cover part of it if the fee agreement meets Florida Rule 4-1.8(a).

### Tools that help without replacing counsel

| Job | Tool | Cost | Limit |
|---|---|---|---|
| Issue-spotting memos, CMS memo summaries, first drafts | General LLM business plans | $20–$125 per seat a month ([HAQQ](https://www.haqq.ai/blog/legal-ai-pricing-2026.html)) | Can invent citations; check against eCFR and CMS FAQs. No customer data without a BAA |
| Signatures and contract repository | Docusign IAM Standard | $45 per user a month, 3-seat minimum ($1,620/year) ([Signeasy](https://signeasy.com/blog/business/docusign-iam-pricing)) | AI review is Enterprise-only |
| Cookie banner and draft privacy policy | Termly $10–$20 per site a month ([PricingSaaS](https://pricingsaas.com/companies/termly)); Osano free or $199/month ([Enzuzo](https://www.enzuzo.com/blog/osano-pricing)) | Low | Not built for HIPAA, TPMO consent or 69O-128. Counsel rewrites the health and insurance sections |
| BAA starting text | HHS sample BAA provisions ([HHS](https://www.hhs.gov/guidance/document/sample-business-associate-agreement-provisions)) | Free | HHS says they are not a complete contract |
| Consent records | TrustedForm: certificates free; 5-year retention $0.06–$0.15 each ([ActiveProspect](https://support.activeprospect.com/hc/en-us/articles/44399426362004-ActiveProspect-Pricing)) | Pennies | 5 years is shorter than enrollment record retention; export and archive |
| Phone and video recording | IntegrityCONNECT free; Recordia $40/month; both with 10-year retention ([Ritter](https://ritterim.com/blog/a-review-of-the-top-call-recording-applications-for-compliant-medicare-business)) | Low | CMS guidance is silent on chat |
| Regulatory monitoring | Federal Register alerts, the public HPMS supplemental list ([CMS](https://www.cms.gov/about-cms/information-systems/hpms/listserv)), CMS email, Florida Administrative Register, DFS newsletter | Free | Paid monitoring (Changeflow $99/month) can wait for a compliance hire ([Changeflow](https://changeflow.com/learn/compliance-monitoring-software)) |
| Lawyer research platforms | CoCounsel ($340–$1,695 a month) ([Costbench](https://costbench.com/software/ai-legal-tools/cocounsel)); Harvey ("not currently priced for solo practitioners") ([Layer3Labs](https://www.layer3labs.io/guides/harvey-ai-pricing)) | High | Built and sold for law firms; skip |

### Affordable counsel, including equity

Florida 2025 averages are about **$427 an hour for corporate work, $395 for business and $222 for "insurance"**, from a secondary summary of Clio data ([GrowLaw](https://growlaw.co/blog/attorney-hourly-rates-fl)). National outside counsel runs $400–$1,500+ an hour, and a light fractional general counsel retainer starts around $1,500–$2,500 a month ([Sartori](https://sartoriglobal.com/insights/guides/fractional-general-counsel-rates-and-models/)).

Firms the research found with the relevant specialties (none vetted):

- **Epstein Becker Green.** Its health-plans group has commented on CMS broker compensation ([EBG](https://ebglaw.com/insights/news/helaine-fingold-quoted-in-finalized-broker-pay-cap-appears-to-exclude-fmos-but-impact-remains-unclear)).
- **Colodny Fass.** A Florida firm that represents agents before DFS; one attorney is a former OIR and DFS senior attorney ([Colodny Fass](https://colodnyfass.com/blog/legal-counsel-for-florida-insurance-agents-and-brokers)).
- **Chambers' Florida insurance regulatory table**, as a shortlist source ([Chambers](https://chambers.com/legal-rankings/insurance-transactional-regulatory-florida-5:472:12326:1)).

Cheaper entry points:

- The **University of Miami Startup Clinic** helps with formation, contracts, terms of service and privacy policies ([UM](https://www.law.miami.edu/academics/experiential-learning/clinics/startup)).
- The **Florida Bar referral service** caps the first 30-minute consultation at $25 ([Florida Bar](https://www.floridabar.org/member/lrs/lrsrules/)).
- **Hogan Lovells' Launch Pad** defers the first $50,000 of fees, then half of the next $100,000, for up to 18 months, repaid with a 7%–15% premium. It targets life sciences and health companies, and whether a Medicare brokerage qualifies is unconfirmed ([Hogan Lovells](https://hlc.com/-/media/hogan-lovells/pdf/2026-pdfs/hlc-launch-pad-2026.pdf)).

Paying counsel in equity is permitted. ABA Formal Opinion 00-418 allows stock in place of cash if the terms are fair, disclosed in writing, the client has a chance to consult independent counsel, and the client consents in writing ([summary](https://ezel.ai/ethics-opinions/aba/00-418-acquiring-ownership-in-a-client)). Florida Rule 4-1.8(a) requires the same three elements, with the client's signed informed consent ([Rule 4-1.8](https://d1tvxue8o4w0fl.cloudfront.net/rule/florida-court-rules/rules-regulating-the-florida-bar/chapter-4-rules-of-professional-conduct/rule-4-1-client-lawyer-relationship/rule-4-18-conflict-of-interest-prohibited-and-other-transactions)).

The practical method is to set a reasonable cash fee first, then issue stock worth that amount at the price recent cash investors paid ([Georgetown JLE](https://www.law.georgetown.edu/legal-ethics-journal/blog/the-ethical-implications-and-practical-concerns-of-equity-billing/)). A bootstrapped Daylight has no priced round, so valuation is the hard part, and Daylight needs its own independent review of the fee agreement. The research found no firm that publicly states it accepts equity. My recommendation:

- Offer equity to the Florida boutique or a fractional general counsel who will be around for years.
- Pay the national specialist opinion in cash or deferred cash.

### Cheaper routes to regulatory answers

- **Carrier compliance teams.** Plans are accountable for TPMO oversight and file agency marketing in CMS's HPMS system, so a carrier's compliance team is the first practical source of interpretation ([Cigna TPMO requirements](https://inform.cigna.com/tpmo-requirements); [AgentTech](https://agenttech.io/blog/agency-medicare-marketing-approval-workflow)).
- **FMO guidance.** FMOs publish free TPMO guidance.
- **CMS's own FAQ.** It is the cheapest authoritative source ([CMS FAQ](https://CMS.gov/files/document/agent-broker-marketing-faqs-10-19-2022.pdf)).
- **NABIP's Southwest Florida chapter.** $536 a year, with Medicare marketing rule resources ([NABIP application](https://nabip.org/media/9948/2025-nabip-membership-application.pdf)).
- **A Florida declaratory statement** under Fla. Stat. 120.565. It is the only binding route found: the agency must answer within 90 days, but the petition and answer are published ([Fla. Stat. 120.565](https://florida.public.law/statutes/fla._stat._120.565)). It covers Florida licensing law, not CMS rules.

Informal answers from carriers or CMS are not safe harbors, so counsel should review them.

| Launch legal budget | Lean | Fully managed |
|---|---|---|
| Corporate formation and documents | Clerky or Stripe Atlas, $427–$819 ([Beancount](https://beancount.io/blog/2026/10/23/stripe-atlas-vs-firstbase-vs-clerky-incorporation-service-comparison-guide)), or the UM clinic | Same, plus counsel review |
| Specialist regulatory review | 20–40 hours at about $400 = $8k–$16k (researcher estimate); part equity or deferred | National rates could double it: $16k–$32k (est.) |
| Ongoing counsel | As needed | Fractional general counsel $1,500–$2,500 a month |
| Tools | $1k–$3k a year | Same, plus Osano Plus |
| **First-year total** | **About $10k–$20k cash before equity offsets** (est.) | **About $38k–$66k** (est.); the researcher's range was $15k–$50k |

Questions that must go to counsel:

1. Whether an AI-generated recommendation from a licensed agency is licensable activity under Florida chapter 626, and whether it satisfies CMS's requirement that agents discuss specific topics.
2. Whether chat is a "call" for recording and retention.
3. TPMO consent design and which vendors are TPMOs.
4. Daylight's HIPAA business-associate status and FTC Health Breach Notification Rule exposure.
5. The final privacy notice and the 69O-128 program.
6. The brand name.
7. The equity fee agreement itself.

The spec's questions Q1–Q7 add to this list.

On the longer-term goal of in-house legal: the first in-house hire is more likely a Medicare compliance analyst (a role agencies already post) than a general counsel. Outside guidance puts the first full-time legal hire around Series B ([OneGC](https://onegc.com/blog/outside-counsel-in-house-fractional-gc); [MyPlanAdvocate posting](https://ats.rippling.com/myplanadvocate/jobs/8f7bd8a5-444c-4803-814e-f0f5bdb502a5)).

## Validation: AI can screen recommendations but cannot certify them

**Bottom line:** no published study shows an LLM reliably picking Medicare plans on its own, and the research on AI judges says they agree with experts only on structured checks. AI can validate the parts of a recommendation that are checkable: is every claim grounded, was every eligible plan scored, does the ranking survive a commission swap. It should not be the final judge of the trade-off narrative a 65-year-old reads.

That is exactly Daylight's design: a deterministic engine for every number and eligibility rule, a two-stage controller, an evaluation harness, and Option B licensed review of each record.

### What the evidence says

The human baseline is weak on precisely the parts Daylight automates. In a 2023–2024 mystery-shopper study of State Health Insurance Assistance Program (SHIP) counselors:

- on average **40% of answers were accurate and complete**;
- accuracy ranged from **26.1%** on whether a specific clinician was in network for a specific plan to 94.3% on Original Medicare versus Medicare Advantage;
- only 44.8% of counselors mentioned D-SNPs to dual-eligible shoppers.

([InsuranceNewsNet summary of JAMA Netw Open 2025](https://insurancenewsnet.com/oarticle/new-findings-from-boston-university-in-the-area-of-health-and-medicine-reported-accuracy-of-medicare-information-provided-by-state-health-insurance-assistance-programs-health-and-medicine))

Those are lookup failures, and a deterministic engine on correct CMS and directory data should beat them. Data quality is its own risk, though: Medicare Plan Finder's 2019 redesign produced wrong prices and drugs, and CMS offered a special enrollment period to affected people ([KFF Health News](https://kffhealthnews.org/aging/website-errors-raise-calls-for-medicare-to-be-flexible-with-seniors-enrollment/)).

LLM failures are different. In a MarketWatch test, ChatGPT analyzed only **3 of 6 qualifying MA plans** and skipped the doctor and pharmacy checks ([MarketWatch](https://www-web.itiger.com/news/2586065263)). In another, Claude stated an eight-month Medigap window instead of six ([MarketWatch](https://www-web.itiger.com/news/2551129421)). Both are failures a two-stage controller can prevent by making "every eligible plan scored" and "doctor, drug and pharmacy checks complete" preconditions for any recommendation.

On AI judges:

- A scoping review found **judge–human agreement of about 0.82–0.93 on structured tasks but 0.47–0.71 on complex reasoning**, and 73.5% of studies did no bias testing ([MedJUDGE, arXiv](https://arxiv.org/pdf/2604.25933)).
- A medRxiv study with five frontier judges and six clinicians found AI–human agreement of κ 0.22 against 0.32 between humans, and strong length bias. An AI judgment cost about $0.12 against $9.17 per human evaluation. The authors call phasing out human evaluation "premature" ([medRxiv](https://www.medrxiv.org/content/10.1101/2025.10.27.25338910.full.pdf)).

### How to validate

| Layer | What it checks | How | Who decides |
|---|---|---|---|
| Data pipeline | CMS files loaded correctly; plan counts, formularies and premiums match the source | dbt tests and Dagster asset checks; sample comparisons with Plan Finder | Software |
| Engine | Arithmetic and eligibility | Unit tests and golden cases | Software |
| Checklist coverage | Every eligible plan scored; doctor, drug and pharmacy checks done | Controller preconditions | Software blocks the recommendation |
| Grounding | Each claim traces to the evidence store | LLM judge from a different model family than the writer, as MedJUDGE recommends | Judge screens; humans sample |
| Neutrality | Ranking unchanged when commissions or carrier names are swapped; Original Medicare versus MA neutrality | Counterfactual suite; persona journeys | Software; publish results |
| Abstention and bias | Says "not sure" when evidence is missing; consistent across demographic personas | Persona runner | Founder sets the criteria |
| Narrative quality | The explanation a 65-plus user reads | Judge plus licensed-agent sample, controlling for length bias | Licensed agent |
| Live review | Every recommendation record at launch | Option B; track the override rate. MedJUDGE suggests review when human overrides exceed 15% (a preliminary threshold) | Licensed agent |
| Outcomes | Rapid disenrollment, complaints, chargebacks | Carrier and agency-management reports | Founder |

The Center for Medicare Advocacy's March 2026 statement to CMS works as a ready-made acceptance list ([CMA](https://medicareadvocacy.org/wp-content/uploads/2026/04/AI-RFI-Statement.pdf)). It calls for:

- neutrality between Original Medicare and MA;
- disclosure of every factor behind a suggestion;
- demographic bias testing;
- no financial ties steering results.

The regulatory context points the same way:

- **CMS.** Ran an RFI seeking AI plan-recommendation tools ([TechTarget](https://www.techtarget.com/healthcarepayers/news/366639417/CMS-solicits-information-on-AI-tools-for-Medicare-plan-selection)). It said in June 2026 that it does not use AI bots to auto-enroll beneficiaries and has no plans to eliminate brokers ([InsuranceNewsNet](https://insurancenewsnet.com/innarticle/cms-no-plans-to-eliminate-medicare-brokers)).
- **NAIC.** Florida has not adopted the NAIC AI model bulletin ([NAIC map](https://content.naic.org/sites/default/files/legal-adoption-map-ai-model-bulletin.pdf)). Carriers in adopting states must do diligence on AI vendors, so expect AI-governance terms in carrier contracts anyway.

Evaluation spend runs about $500–$1,500 a month during active development (researcher estimate). Batch pricing halves it, and Batch is usable because evaluations run on synthetic personas outside the HIPAA org.

## The AI-native stack is real for internal work, not for regulated decisions

**Bottom line:** an "AI-native company" is real in a narrower sense than the marketing suggests: a small human team supervising agents for internal work. Paperclip is a genuine, popular open-source tool for that. It is also eight months old, maintained by a pseudonymous developer, offers no BAA, and had a critical remote-code-execution bug in 2026. Use it for engineering and research chores that touch no health data, behind a hardened, non-public install. Keep it away from beneficiaries, enrollments and anything with real customer data.

### What Paperclip is

Paperclip is an MIT-licensed, self-hosted control plane that organizes the coding agents you bring (Claude Code, Codex, Gemini CLI and others) into an org chart. It adds:

- goals and tickets;
- scheduled "heartbeats";
- per-agent monthly budgets that warn at 80% and pause at 100%;
- an append-only audit log;
- a human "board" that approves agent hires.

([paperclip.ing](https://hn.jakechampion.name/reader/https://paperclip.ing))

Maturity and adoption:

- Created March 2, 2026 by the pseudonymous @dotta, with no company, funding, hosted tier or SLA. It had about 70,000 GitHub stars and nearly 5,000 open issues by June ([Ry Walker](https://rywalker.com/research/paperclip)).
- Its creator called it "very, very early" and named missing multi-user support a "huge gap" ([ZenML](https://www.zenml.io/llmops-database/open-source-agent-orchestration-platform-for-multi-agent-business-automation)).
- An independent test found the orchestration useful but the output unreliable, including "confident but unsourced or fabricated statistics." It concluded production work needs human review at every step ([Fast.io](https://fast.io/resources/paperclip-ai-review-2026.md)).

Security history:

- **CVE-2026-41679 (CVSS 10.0).** Let an attacker on a network-reachable install with open registration get a board API key and run OS commands as the server. It was fixed in v2026.416.0, and Rapid7 published a Metasploit module ([The Hacker News](https://thehackernews.com/2026/08/paperclip-ai-flaws-let-attackers-run.html?hl=en)).
- **A DNS-rebinding flaw (CVSS 9.6)** in the default local mode let a malicious web page run commands with the developer's privileges. It was fixed in 0.3.1, which adds hostname validation in local mode ([Infosecurity Magazine, Aug 5, 2026](https://www.infosecurity-magazine.com/news/paperclip-ai-vulnerabilities-rce/)). This one matters most for a laptop install.

Since the founder appears to have it installed, the immediate steps are:

1. Confirm the installed version includes both fixes (v2026.416.0 or later, and the 0.3.1 local-mode fix).
2. Turn off open registration.
3. Keep it off the public internet (VPN or Tailscale only).
4. Run it under a low-privilege account with no production secrets.
5. Treat imported agent configurations as code that needs review.

The cost is a $20–$50 virtual machine plus agent spend of roughly $200–$1,000 a month for a 3–5 agent setup, plus 2–4 hours a week of upkeep ([Fast.io](https://fast.io/resources/paperclip-ai-review-2026.md), unsourced estimates there) (est.). The founder already runs Codex on the backend and data layer, so Paperclip's main value is coordinating those agents, not adding new capability.

| Good fit for agents (no customer data) | Only with a human sign-off | Never |
|---|---|---|
| Engineering tickets with code review; CMS public-data pipeline chores; competitive and regulatory research; weekly summaries of CMS and DFS feeds; eval runs on synthetic personas; commission statement matching | Marketing drafts (then carrier filing where required); B2B partner emails; plan-document extraction with verification passes | Anything with PHI or real customer data; consumer outreach; recommendations or messages to beneficiaries; enrollments; carrier contracting, attestations or AHIP |

eHealth's numbers show where the economics of automation sit. Its $598 AEP cost per MA member split into **$372 of marketing and $226 of customer care and enrollment** ([eHealth FY2025 results](https://mma.prnewswire.com/media/2920363/eHealth_2025_Results.pdf?p=original)). Automating advice and enrollment attacks roughly 40% of a digital broker's acquisition cost (researcher inference). Paid media still has to be won by channel choice.

GoHealth's 2026 Chapter 11, after heavy telesales and purchased-lead acquisition, is the cautionary contrast ([GoHealth 8-K](https://www.sec.gov/Archives/edgar/data/0001808220/000162828026049063/exhibit992-pressrelease.htm)).

## Launch cost: about $14k–$27k one-time on the lean path

**Bottom line:** the lean, BAA-correct MVP costs about **$14k–$27k one-time, $850–$2,450 a month off-season and $1,300–$5,500 a month in AEP** (est.). The fully managed version costs about **$39k–$81k one-time, $9.6k–$20k a month off-season and $12.5k–$38k in AEP**, before quote-only vendors (est.). Infrastructure and tokens are not the big lines. Counsel, assurance work and, at volume, licensed review are.

Assumptions:

- 50–150 completed decisions a month off-season and 300–1,500 in AEP (the AEP range is the researchers'; the off-season range is mine).
- About $1–$2 per decision on Sonnet 5.5 and $2–$4 on Opus 5.5 (researcher estimate; the US-only 1.1x is within range).
- About 10 minutes per licensed review, which is my assumption; shadow mode should measure it.

Every total below is my roll-up of the sourced unit prices cited in earlier sections.

| Area | Lean choice | Fully managed choice | One-time, lean | One-time, managed | Monthly lean (off-season / AEP) | Monthly managed (off-season / AEP) | Basis |
|---|---|---|---|---|---|---|---|
| Model tokens | Sonnet 5.5 cached, US-only; Haiku 5.5 classifier | Opus 5.5 with thinking | $50–$150 (plan-document extraction) | $50–$150 | $50–$300 / $300–$3,000 | $100–$600 / $600–$6,000 | Est. on verified prices |
| Evals and judges | Synthetic personas in a non-HIPAA org; promptfoo or Braintrust Starter | Braintrust Pro (in hosting row) | — | — | $200–$500 / same | $500–$1,500 / same | Researcher est. |
| Hosting, Postgres, pipelines, tracing | App, self-hosted Langfuse, Dagster OSS and dbt Core on the BAA cloud; RDS or Neon Scale | Vercel Pro + BAA $370; Supabase HIPAA about $950; Langfuse Pro $199; Braintrust Pro $249; Dagster and dbt Starter ([Dagster](https://support.dagster.io/articles/3171123463-dagster-solo-and-starter-pricing-updates-may-2026); [dbt](https://getdbt.com/pricing)) | — | — | $200–$550 / $300–$800 | $2,000–$2,600 / $2,200–$3,000 | List prices; usage est. |
| Edge, bot and cost controls | CloudFront + WAF Bot Control; Turnstile; Redis; classifier | Cloudflare Enterprise with BAA | — | — | $35–$95 / $50–$150 | $3,000–$8,500 / same | AWS list; Cloudflare third-party est. |
| Email, SMS, sign-in | Paubox free or SES; Twilio Verify at checkout; Cognito or self-built | Paubox Pro; Twilio Security Edition; Clerk Enterprise | — | — | $0–$115 / $104–$150 | $104–$208 + quotes | Partly unpriced |
| Medicare operations | MedicarePro CRM $45–$55 ([EnrollHere](https://enrollhere.com/blogs/medicare-crm-pricing-guide)); IntegrityCONNECT or Recordia; TrustedForm; FMO-provided enrollment platform; CSG through the agency system | AgencyBloc plus Commissions+ module ([Costbench](https://costbench.com/software/insurance-agency-management/agencybloc/)); AgentTech; CSG direct feed ([CSG](https://www.csgactuarial.com/news/p5bbsrrmrn8u0n140ookei6zz0xgc2)); licensed enrollment platform | $0 | $1,500–$3,500 | $45–$100 + CSG quote | $380–$680 + quotes | AgencyBloc prices conflict, $25 vs $109–$130 per user (**confirm**) |
| Licensed review (Option B) | Founder reviews: $0 cash, capacity about 300 decisions a month | Part-time licensed reviewer at about $53 an hour ([Salary.com](https://www.salary.com/research/salary/hiring/medicare-insurance-agent-salary)) | — | — | $0 / $0 | $450–$1,350 / $2,650–$13,250 | My est. |
| Legal | Fixed-scope specialist reviews, part equity; LLM seat; Termly | National-rate counsel; fractional general counsel; Osano Plus | $8,000–$16,000 | $16,000–$32,000 | $20–$145 | $1,825–$2,825 | Est. on sourced rates |
| Security assurance | Pen test; in-house red-team; HHS SRA Tool | Larger pen test; external AI red-team; SOC 2 Type 1; compliance platform | $3,000–$7,200 | $18,000–$38,000 | $0 | $625–$1,000 | Vendor prices; est. ranges |
| Insurance | Individual Medicare E&O, $374 a year ([NAPA](https://www.napa-benefits.org/agentsolutions/errors-and-omissions)); $1M cyber | Agency E&O, $1,530–$2,330 a year; cyber; tech E&O | — | — | $200–$530 | $545–$1,030 + tech E&O | E&O sourced; cyber est. |
| Company, licensing, memberships | Delaware C-corp and Florida LLC; 2-40 license; AHIP; NABIP | Same | $950–$1,350 | $950–$1,350 | $85–$120 | $85–$120 | Sourced fees |
| User research | 15 moderated interviews | Plus a Prolific survey or AI-moderated prepaid credits | $1,700–$1,900 | $2,500–$5,500 | — | — | Sourced fees; incentive est. |
| **Total** | | | **About $14k–$27k** | **About $39k–$81k** | **About $850–$2,450 / $1,300–$5,500** | **About $9.6k–$20k / $12.5k–$38k, plus quotes** | Est. |

Not in the totals:

- the go-to-market channel proof, about $6k–$15k over three months (researcher estimate);
- Paperclip internal operations, $220–$1,050 a month (est.);
- founder pay;
- design and brand work;
- postage;
- the Google health-insurance advertiser certification;
- every quote-only item: CSG Medigap rates, the SunFire, Convey or CSG enrollment platform, Twilio Security Edition, Clerk Enterprise and tech E&O.

Those quote-only items are the largest unknown, and the research did not get a single quote. Over a first year of roughly ten off-season and two AEP months, the lean path comes to about **$25k–$62k plus the channel proof**. The fully managed path comes to roughly **$160k–$360k** (my arithmetic).

At the illustrative $240 per AEP conversation, the lean AEP run-rate equals the year-one commission from about 5–23 completed conversations a month (my arithmetic). So acquisition cost, not infrastructure, decides whether the pilot pays. Commission cash also lags the sale: Humana pays in two parts around CMS validation, and UHC trues up in mid-January.

Founder review capacity is the hidden ceiling of the lean path. At 10 minutes per review, 1,500 AEP decisions a month is about 250 hours, more than a solo founder running several departments can absorb (my estimate). Above roughly 300 decisions a month, budget for a part-time licensed reviewer.

## Go-to-market: prove turning-65 direct mail before ads or partners

**Bottom line:** prove one consumer channel first: turning-65 direct mail in Collier County, sending people to the self-serve flow, with Google Search as the backup. Start local partner relationships now because they take months, but don't make them the three-month proof. Never buy or sell leads.

"Origami" is almost certainly **Origami (origami.chat, also sold as Origami Agents)**, an AI prospecting tool at **$99–$399 a month**. It suits finding Naples-area partners and must never be used for consumer outreach.

### The rules that shape every channel

The CY2027 rule changes took effect for marketing on October 1, 2026:

- The 48-hour scope-of-appointment wait is gone, though a scope of appointment is still required.
- The TPMO disclaimer must now come "before plan benefits are discussed" rather than in the first minute ([RISE Health](https://www.risehealth.org/insights-articles/7-marketing-changes-in-the-2027-medicare-advantage-final-rule/)).
- Several sources say the new disclaimer drops the reference to State Health Insurance Programs ([Spark, Apr 3, 2026](https://sparkadvisors.com/resource/cms-final-rule-2027-what-brokers-need-to-know); [LeadGen Economy](https://www.leadgen-economy.com/blog/cms-cy2027-medicare-final-rule-soa-kill-lead-gen.md)), while Spark's May 2026 disclaimer page still shows it ([Spark](https://help.sparkadvisors.com/en/articles/12012231-disclaimers)). **Confirm** the exact wording with counsel.

Unchanged rules that close off cheap shortcuts:

- No calls, texts or door-knocking without prior permission for that method.
- Nominal gifts are capped at $15 per item and $75 a year, with no cash and nothing conditional on enrolling ([Open Exam Prep](https://open-exam-prep.com/study-guides/ahip-medicare/cms-marketing-rules-scope-of-appointment/permitted-prohibited-marketing-activities)).
- CMS one-to-one consent still stands even though the FCC's version was vacated ([TCPAWorld](https://tcpaworld.com/2025/03/11/even-with-fcc-11-gone-the-cms-11-rule-is-still-standing/)).
- Under Fla. Stat. 626.112(8), Daylight may pay an unlicensed referrer only if payment does not depend on the referral buying a policy ([Radey Law](https://www.radeylaw.com/2016/10/05/dfs-summarizes-referral-fee-restrictions/)). This source dates from 2016; **confirm** the current text.

### Recording and retention: sources conflict

This is the most important conflict in the research.

- What is settled: a law-firm summary of the final rule confirms that retention for **marketing and sales call recordings drops from 10 years to 6**, with marketing changes effective October 1, 2026 ([Crowell & Moring](https://www.crowell.com/en/insights/client-alerts/cms-finalizes-cy-2027-medicare-advantage-and-part-d-rule-key-implications-for-plan-sponsors)). It does not address chat or say whether enrollment records differ.
- Ritter and ThinkAdvisor summarize the CY2027 rule as requiring recording **only for calls that result in an enrollment**, with marketing-call retention cut to **6 years** (audio for 3, transcript for 3) and enrollment records kept **10 years** ([Ritter, Apr 15, 2026](https://ritterim.com/blog/cms-improves-plan-transparency-and-choice-with-2027-ma-and-part-d-final-rule); [ThinkAdvisor](https://www.thinkadvisor.com/amp/2026/04/03/medicare-advantage-regulators-lighten-agent-sales-rules-for-2027/)).
- Other summaries say sales and marketing calls must still be recorded but kept 6 years, with enrollment calls at 10 ([LeadGen Economy](https://www.leadgen-economy.com/blog/cms-cy2027-medicare-final-rule-soa-kill-lead-gen.md)).
- A vendor page modified in October 2026, and CMS's own 2022 FAQ, still say 10 years for sales calls ([AgentTech](https://agenttech.io/blog/cms-call-recording-requirements); [CMS FAQ](https://CMS.gov/files/document/agent-broker-marketing-faqs-10-19-2022.pdf)). These predate or lag the rule.

What remains open is whether only enrollment calls must be recorded, how long enrollment records are kept, and whether chat counts as a call. **Confirm** with counsel against the Federal Register text (document 2026-06600). Update spec §5.2.9, which still states ten years for sales calls. The sealed compliance archive design works whichever answer holds.

### Channels compared

| Channel | Can it reach 64–65-year-olds? | Main constraint | Unit cost (sourced) | Verdict |
|---|---|---|---|---|
| Turning-65 direct mail | Yes, through age lists; ask vendors where birth dates come from ([4over4](https://www.4over4.com/article/reach-prospects-turning-65-with-daily-medicare-mailers)) | Disclaimers; plan-specific pieces need carrier review and a material ID | List about $50 per 1,000 records ([Spark](https://help.sparkadvisors.com/en/articles/12012371-direct-mail-guide)); print about $0.18 per postcard; postage not sourced | **Prove first** |
| Google Search | By search intent, not age | Health-insurance advertiser certification, with G2RS first ([Google Ads policy](https://support.google.com/adspolicy/answer/15597838)) | Finance and insurance average $3.39 per click and $74.44 per lead ([WordStream](https://wordstream.com/blog/2026-google-ads-benchmarks)); carrier-brand Medicare terms $7–$16 per click ([AdTargeting](https://adtargeting.io/industry/health-insurance-keywords)) | Backup; start certification now |
| Meta | No. The Special Ad Category bans age, gender and ZIP targeting and sets a 15-mile radius minimum ([Data Axle](https://www.data-axle.com/resources/blog/meta-special-ad-categories-rules/)) | Health-data limits block lower-funnel optimization ([Search Engine Land](https://searchengineland.com/meta-ads-restrictions-health-wellness-campaigns-453094)) | Not sourced | Skip for the proof |
| Bought leads | — | One-to-one consent; cold-contact bans | Low-reliability source only | Don't |
| Local partners (RIAs, CPAs, HR, 55+ communities) | Indirectly | No per-enrollment pay to unlicensed partners; CMS referral cap $100 MA; written consent naming Daylight | Low cash, slow | Start now; prove later |
| Educational events | Yes, by venue | No meals; accommodation notices; scope-of-appointment collection now allowed | Not sourced | Trust-builder, labor-heavy |

### B2C versus B2B2C

The precedents point both ways:

- **Chapter (B2B2C).** Valued at $1.5B, it avoids direct-to-consumer advertising and grew through wealth managers and health systems ([Fierce Healthcare](https://www.fiercehealthcare.com/payers/medicare-navigation-startup-chapter-pockets-75m-expand-health-system-partnerships)). Its partners were told its advisers "earn identical compensation irrespective of the selected plan or carrier" ([Mercer Advisors](https://www.merceradvisors.com/press/mercer-advisors-partners-with-chapter-to-provide-holistic-healthcare-guidance-to-clients/)).
- **Healthpilot (B2C).** Self-serve, payer-agnostic, with a minority investment from Humana ([Healthcare Dive](https://www.healthcaredive.com/news/humana-minority-investment-healthpilot/721663/)).

Daylight's positioning (self-serve like Healthpilot, more trustworthy, more automated than Chapter) makes a consumer channel the right first proof, because it tests the product itself. Partners are the scale channel. The pitch to partners that the evidence supports is neutrality, shown by the commission-swap test results.

Direct mail is the recommended proof for four reasons:

- it is the only channel that can target 64–65-year-olds directly;
- monthly birthday cohorts give clean, repeatable samples;
- the consumer initiates contact, which avoids consent and telemarketing risk;
- it drives people into the self-serve flow.

The weakness is that no source gave Medicare direct-mail response rates, so the first cohort is the measurement.

### Origami

Origami's official pricing on November 7, 2026 is Starter $99, Pro $199 and Max $399 a month. Contact data is billed at cost, $0.066 per verified email and $0.33 per phone, and there is a 7-day trial ([Origami pricing](https://origami.chat/pricing)). Older listings at $29 and $129 are out of date ([Capterra](https://www.capterra.com/p/10037370/Origami/)).

Its agents search Google Maps, license registries and review sites, which suits local partners that databases cover poorly. A competitor warns that open-web contacts need accuracy checks and that someone must review each message sent under your name ([Valley](https://www.joinvalley.co/blog/origami-agents-vs-valley)). Apollo's free tier may cover fewer than 200 partner targets ([Origami blog](https://origami.chat/blog/agentic-sales-tools-early-stage-companies-2026)). A separate product, Origami Risk, is insurance risk-management software ([xpay](https://www.xpay.sh/saas-pricing/origami-risk/)). **Confirm** which one the founder saw.

### Market validation beyond the pilot

| Tool | Best for | Cost | Caveat |
|---|---|---|---|
| User Interviews | Moderated 45–60 minute interviews | $49 per completed session pay-as-you-go, plus incentive and a 3% fee ([Koji](https://www.koji.so/blog/user-interviews-pricing-2026)) | Depth of the 65-plus panel undocumented |
| Respondent | Same | $40 per consumer session plus incentive ([Koji](https://www.koji.so/blog/respondent-pricing-2026)) | Same |
| Prolific | 10-minute surveys at scale | Platform fee of 42.8% or 33% of participant pay; sources conflict ([Koji](https://www.koji.so/blog/prolific-pricing-2026); [CleverX](https://cleverx.com/blog/prolific-review-2026)) | Weak for moderated research |
| Conveo | AI-moderated interviews | $5 a minute, $5,000 prepaid minimum ([Usercall](https://www.usercall.co/post/ai-moderated-interview-cost-2026)) | Older users may balk at an AI moderator |
| Listen Labs | AI-moderated at scale | About $20,000 a year (competitor estimate) ([Koji](https://www.koji.so/blog/listen-labs-pricing-2026)) | Too costly now |

A first round of 15 moderated interviews costs about $1,700–$1,900 at a $75 incentive. A 200-person Prolific survey costs about $530–$570 (researcher estimates). National panels won't reproduce Naples, so add a few local recruits.

Run the proof from January to March 2027, inside the MA Open Enrollment Period and turning-65 windows (**confirm** dates on Medicare.gov):

- monthly cohorts of about 1,000 pieces;
- a unique URL and phone number per creative.

Measure cost per completed self-serve recommendation and cost per enrollment. The researchers' target is under about $400 per MA enrollment, which leaves room for licensed review under the $725 cap.

## Spin-up: four to eight weeks and under $3,000 to a first legal enrollment

**Bottom line:** starting November 9, 2026, the realistic first legal enrollment is mid-December 2026 to January 2027, through non-AEP windows. Direct first-year cash excluding counsel and software is about $1,700–$3,000. The founder should take the Florida 2-40 health license now and serve as agent in charge. Use a Delaware C-corp parent with a Florida LLC agency subsidiary, subject to counsel. Pick an agency and consumer brand without "Medicare" in it.

### Entity

A Delaware C-corp costs $427–$819 through Clerky or Stripe Atlas ([Beancount](https://beancount.io/blog/2026/10/23/stripe-atlas-vs-firstbase-vs-clerky-incorporation-service-comparison-guide)). Keeping it costs:

- the official minimum franchise tax: $175 under the authorized-shares method or $400 under assumed par value, plus a $50 annual report ([Delaware](https://corp.delaware.gov/frtax/));
- a registered agent at about $100–$300 a year.

File on the assumed-par-value method to avoid an inflated bill. A secondary source's "roughly $300 minimum" conflicts with the official figures; use the official ones. A Florida LLC costs $125 to form and $138.75 a year, with a steep late fee after May 1 ([Sunbiz](https://dos.fl.gov/sunbiz/forms/fees/)).

Florida requires every owner, officer, director and LLC manager to be listed on the agency application, and fingerprinted unless licensed and appointed ([Fla. Stat. 626.172](https://m.flsenate.gov/Statutes/626.172)). Keeping the licensed agency in a subsidiary stops every new investor board seat from triggering a DFS filing (researcher inference; counsel should confirm).

### The founder's license

The **2-40 Health** license covers Medicare health products with 40 hours of prelicensing. A resident license requires bona fide Florida residency, no resident license elsewhere, and an exam at a physical Pearson VUE center ([DFS 2-40 checklist](https://myfloridacfo.com/docs-sf/insurance-agents-and-agency-services-libraries/agents-docs/licensure/agents-adjusters/2-40-resident-health-agent-license.pdf); [DFS exams](https://myfloridacfo.com/division/agents/licensing/agents-and-adjusters/exams)). Costs:

- course about $99 ([OLTraining](https://oltraining.com/pre-licensing/40-hour-2-40-health-insurance-agent-pre-licensing-course-ins022fl40));
- application $50 plus $5 per line ([NIPR](https://nipr.com/licensing-center/state-requirements/florida-resident-licensing-individual));
- fingerprints $52.50 plus tax through IdentoGO only ([DFS](https://myfloridacfo.com/Division/Agents/Licensure/Agents-Adjusters/fingerprinting.htm));
- exam about $44 (secondary source).

A founder living outside Florida would need a home-state resident license plus a Florida nonresident license.

### The agency license and name

Every agency transacting insurance in Florida needs an agency license (type 21-05) with a licensed, appointed agent in charge. The only exemption is a single agent working under their own name ([DFS](https://myfloridacfo.com/division/agents/compliance/insurance-agencies)). If the agent in charge leaves, a replacement is due within 30 days, and the license expires automatically after 90 days without one. That is one more reason the founder should hold a license even after hiring.

The statute also says each agency location must be in the "active full-time charge" of a licensed and appointed agent, and that unlicensed staff may not initiate contact to solicit insurance ([Fla. Stat. 626.0428](https://m.flsenate.gov/Statutes/626.0428)). Two counsel questions follow: what "full-time charge" means for a founder running several departments of an online agency, and whether AI-initiated messages count as solicitation by an unlicensed representative.

The agent in charge is accountable for violations by agency personnel. That reinforces Option B review of what the AI tells beneficiaries. No agency application fee appears in the statute; **confirm** with DFS.

On the name:

- DFS may reject names that imply a government entity.
- CMS's marketing rule does not ban the word. It prohibits using the Medicare name, the CMS logo or federal products and information "in a misleading way," and the Medicare card image needs CMS authorization ([42 CFR 422.2262](https://www.law.cornell.edu/cfr/text/42/422.2262); [TCPAWorld summary of the 2023 rule](https://tcpaworld.com/2023/04/06/cms-new-rules-tpmos-saved-for-now-updated-and-required-disclaimers-and-much-more/)). Plans enforce this on agents through oversight.
- An FMO's compliance guide says "Medicare" in a name or logo needs a "non-government entity" tagline directly beneath it ([Spark](https://help.sparkadvisors.com/en/articles/12012231-disclaimers)). **Confirm**; this is FMO guidance, not rule text.

The founder's wariness about the daylightmedicare.com brand is reasonable: the name is not prohibited, but "Medicare" in a brand invites a misleading-use review by every carrier that files Daylight's marketing, and by DFS. Whether the domain can serve as a redirect was not researched (counsel).

### Certification, contracting and E&O

AHIP's 2027 course (Medicare plus fraud, waste and abuse) costs $175 list or $125 through FMO or carrier discount links ([Spark](https://help.sparkadvisors.com/en/articles/15118113-ahip-2027)). Several carriers' 2027 trainings cover the rest of 2026 ([Cornerstone](https://cornerstoneseniormarketing.com/2027-certifications/)). Contracting takes "a few days" but can stretch to weeks near AEP, and a writing number issues only at ready-to-sell status ([Ritter/Medicareful](https://medicareful.ritterim.com/blog/contract-get-appointed-to-sell-with-health-insurance-companies)).

UHC requires $1M/$1M E&O ([SuranceBay](https://support.surancebay.com/hc/en-us/articles/214271448-E-O-Carrier-Requirements)). Individual Medicare-only E&O at that limit is about $374 a year, and a small agency policy is $1,530–$2,330 ([NAPA](https://www.napa-benefits.org/agentsolutions/errors-and-omissions)). E&O and D&O markets are adding broad "absolute" AI exclusions ([IIABA](https://www.independentagent.com/vu_resource/artificial-intelligence-exclusions-are-creeping-into-insurance-but-cyber-policies-arent-the-issue-yet/)). Disclose the AI engine on the application and get written confirmation that licensed review of an AI recommendation is a covered professional service.

### Timeline

| Target date (est.) | Step | Cost |
|---|---|---|
| Nov 9–11, 2026 | Form Delaware C-corp parent; get EIN | $427–$819 |
| Nov 9–16 | 2-40 course; DFS application; fingerprints | About $99 + $57.45 + $52.50 and tax |
| Nov 16–20 | Pearson VUE exam | About $44 |
| Nov 16–30 | Florida LLC agency subsidiary; FEIN | $125 |
| Nov 23–Dec 4 | License issues; NPN appears (DFS publishes no processing time) | $0 |
| Nov 20–Dec 4 | Bind $1M/$1M E&O; complete AHIP 2027 | About $374; $125 |
| About Dec 1 | Agency license (21-05) with founder as agent in charge | No fee found (**confirm**) |
| Dec 1, 2026–Jan 15, 2027 | Carrier contracting through the hybrid FMO; carrier certifications; ready-to-sell | Resident appointment fees typically carrier-paid |
| Mid-Dec 2026–Jan 2027 | **First legal enrollment** (MA Open Enrollment Period, turning-65, special enrollment periods, Medigap) | — |
| Mar 1 and May 1, 2027 | Delaware franchise tax and report; Florida annual report | $225–$450; $138.75 |
| Jun–Aug 2027 | AHIP for plan year 2028; carrier certifications; contract extra carriers by August | About $125–$175 |
| By Oct 1, 2027 | Compliant marketing, disclaimer placement, scope-of-appointment capture, recording and retention | — |
| Oct 15–Dec 7, 2027 | First full AEP (plan year 2028) | — |

The biggest schedule risks:

- DFS processing time and fingerprint clearance, which can take up to 45 days if prints are rejected twice;
- Pearson VUE seats near Naples;
- late-AEP carrier backlogs;
- carriers' willingness to contract with a brand-new agency.

## Decisions to make, in order

| # | Decision | Options | Recommendation | Why | Blocks | By when |
|---|---|---|---|---|---|---|
| 1 | Founder licensing | Founder licenses, or hire an agent first | Founder takes the 2-40 now and serves as agent in charge | About $800 all-in with AHIP and E&O; founder becomes the fallback agent in charge under the 90-day rule | Agency license, contracts, first enrollment | Start Nov 9, 2026 |
| 2 | Entity structure | One entity, or Delaware parent plus Florida LLC agency | Parent plus subsidiary, counsel to confirm | Keeps the DFS roster stable as investors join; contains regulatory exposure | Agency license, carrier contracts | Nov 16, 2026 |
| 3 | Brand and agency name | "Daylight Medicare", or a name without "Medicare" | No "Medicare" in the legal or consumer name; use the word descriptively | Not banned, but invites misleading-use review by DFS and every carrier that files Daylight's marketing; possible tagline duty (confirm) | Agency application, carrier filings, mail creative | Before agency application, about Dec 1 |
| 4 | FMO or direct | Full FMO, direct only, or hybrid | Hybrid: agency-owned contracts, immediate vesting, open release, no assignment of commissions; go direct carrier by carrier from Q1–Q2 2027 | Same street commission either way; overrides need production history; FMO speeds contracting | Contracting, first enrollment | Choose the FMO by Dec 1, 2026 |
| 5 | D1: cloud and region | AWS or Google Cloud | AWS, one US region, unless there is a strong Google reason | Free self-serve BAA; Bedrock as second model path; cheap WAF edge | BAAs, edge, deployment | Nov 30, 2026 |
| 6 | D2: edge | Cloudflare Enterprise with BAA, or cloud edge plus Turnstile | CloudFront + WAF Bot Control scoped to chat, plus standalone Turnstile | About $35–$95 a month against about $3k–$8.5k (est.); confirm AWS HIPAA eligibility | Gate 1 | With D1 |
| 7 | Model access | Anthropic direct, Bedrock, or both | Anthropic HIPAA-ready org (Opus, Sonnet and Haiku 5.5; no Covered Models on health-data paths) as primary; Bedrock as second allowlisted path; separate non-HIPAA org for evals | Self-serve, list price; HIPAA enablement is permanent per org; Covered Models need 30-day retention | Gate 1 allowlist | Gate 1 |
| 8 | D3: budget ceilings and provider tier | Pool sizes and monthly model budget | Lean budget about $300 a month off-season and about $3,000 in AEP (est.), refined in shadow mode; upgrade the Anthropic tier before AEP | The Build tier caps at $1,000; a tier cap pauses usage until the 1st | Gate 1 | Gate 1; tier by Aug 2027 |
| 9 | D4: safety cap | 20× the persona-runner estimate, or another value | Measure with the persona runner first, then apply 20× | The research estimates differ about tenfold | Gate 1 | Gate 1 |
| 10 | D5: trace contract | Amend or not | Amend for numeric usage fields only | Shadow-mode cap needs them; no content | Shadow mode | Before pilot traffic |
| 11 | D6: record Option B | Record now or later | Record now | Carriers, the E&O underwriter and counsel will ask how the agent of record attests | Gate 2, E&O application | Dec 2026 |
| 12 | Email and sign-in vendors | Postmark, Paubox or SES; Clerk, Cognito or build | SES or Paubox for anything that might carry health information; Postmark only for health-free sign-in links if counsel agrees; Cognito or self-built passwordless | Postmark signs no BAA; Clerk and Auth0 BAAs are Enterprise-only | Gate 2 checkout | Before the checkout build |
| 13 | Counsel | One big firm, a boutique mix, or a fractional general counsel | Florida insurance-regulatory boutique plus a fixed-scope national CMS marketing opinion; equity under Rule 4-1.8(a) with independent review; ask about deferral | Three specialties at the lowest credible cost | Gate 2, public launch | Engage in Dec 2026 |
| 14 | Chat retention | Ephemeral only, or a sealed archive | Build the sealed compliance archive now; counsel sets retention | CY2027 retention sources conflict; retrofitting costs more | Gate 2 | Before checkout |
| 15 | First channel | Direct mail, Search, Meta or partners | Turning-65 direct mail; apply for Google certification as backup | Only age-targetable channel; consumer-initiated; tests the product | Proof of acquisition cost | First cohort Jan 2027 |
| 16 | Insurance | E&O only, or E&O plus cyber plus AI endorsement | Individual E&O now; agency E&O, cyber and written AI coverage before public launch | $1M/$1M carrier minimum; AI exclusions spreading; E&O excludes cyber | Contracting; public launch | E&O by Dec 1; rest before Gate 2 |
| 17 | Paperclip | Broad use, internal only, or remove | Internal and health-data-free only; patched, private, closed registration | CVSS 10.0 history; no BAA | Security posture | This week |
| 18 | SOC 2 and Vanta/Drata | Now or later | Later, when a carrier or partner asks; HHS SRA Tool now | About $10k–$25k first year (est.) | Gate 3 | When asked |

## What to automate and what to keep human

| Area | Automate | Keep human | Why |
|---|---|---|---|
| Plan math and eligibility | Deterministic engine (no AI) | — | The model never does arithmetic or decides eligibility |
| Recommendation writing | AI drafts from grounded evidence; software validates | A licensed agent reviews every record (Option B) | No evidence AI can certify trade-offs; the agent in charge is accountable |
| Quality assurance | Eval harness, cross-family judges on structured checks, commission-swap and abstention tests | Setting acceptance criteria; reviewing samples and override trends | Judge agreement drops on complex reasoning |
| Enrollment | Submission rails after checkout and step-up identity | The person's explicit permission; agent-of-record attestation | Outbound actions require a software gate plus permission |
| Consumer contact | Transactional messages the person asked for | Any marketing contact, and the decision to authorize outreach | Unsolicited-contact bans, one-to-one consent, Florida telemarketing law |
| Partner outreach | Research and drafts (Origami or Apollo) | Approving each message | Open-web data errors; brand trust |
| Marketing | Drafts, pre-screen checklist, filing log | Final approval and carrier filing | Carriers file agency marketing in HPMS |
| Commissions | Reconciliation, chargeback detection, plan commission-status table on the fulfillment side | Carrier disputes and contract negotiation | Commission data never enters model context |
| Abuse and cost | Edge rules, allowances, friction ladder, kill switches, alerts | Weekly review of the 20 costliest sessions; incident calls | Spec §4 |
| Compliance and legal | Regulatory-feed summaries, issue-spotting memos, first drafts | Counsel's decisions; agent-in-charge duties; licensing filings | Not legal advice; personal accountability |
| Security program | Evidence collection, dependency and secret scanning | Named security official; access reviews; incident decisions | HIPAA requires a named official |
| Engineering | Coding agents with review, including Paperclip-coordinated work | Merge approval; any change to health-data paths | Branch protection and BAA boundaries |
| Licensing and contracting | DFS and NIPR tracking, renewal reminders | Signatures, background disclosures, AHIP exams | Personal attestations |

## Conclusion

The tools turned out to be the easy part, and three findings change the shape of the plan. First, direct carrier contracting is a scale move, not a launch move. "Automate FMO functions" should start with the parts that are software (commission-status tracking, reconciliation, compliance logs) and leave hierarchy status until Daylight has a book worth negotiating with. Second, the cheapest way to use frontier AI with health data is also the most defensible: self-serve BAAs at list price. The compliance risk sits in quiet leaks, such as a fallback to an uncovered provider, a Batch call, a verbose log or an email vendor without a BAA, not in model access. Third, a neutral recommender's year-one revenue per conversation (about $240, illustrative) sits well below eHealth's $598 acquisition cost. Acquisition cost and Medigap mix will decide the business, not infrastructure.

That makes the first quarter of 2027 a measurement quarter, not a growth quarter. The outputs to aim for:

- a real per-decision token cost from shadow mode, to set D3 and D4;
- a real minutes-per-review figure, to set when Option B needs a second agent;
- a real cost per enrollment from monthly direct-mail cohorts;
- written answers from counsel on chat retention and the AI "discuss" question.

With those numbers in hand by summer 2027, the August contracting deadline for the next AEP becomes a decision about scale rather than a scramble to launch.
