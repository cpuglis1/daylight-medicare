# Unnamed Medicare company — architecture review

This is the ground-up company and software blueprint: broad Medicare data/comparison, self-directed conversational research, a licensed transaction, and continuing service. No company name has been selected. Operating model revised October 17, 2026.

**Architecture version 1.2:** competitive position and distribution added October 17, 2026.

**Founding decision 4: self-directed research, licensed transaction.** The deterministic engine ranks using the person's stated criteria and verified data; the AI explains without reordering, adding or removing options. Full results and exclusions remain available. Ready to purchase opens a licensed, appointed agent-of-record session with the full transcript, profile and comparison snapshot for required review, re-verification and submission/authorization.

**Primary operating metric: human minutes per effective, retained policy.** Seasonal agent-response targets and scheduled fallback support the purchase handoff. Carrier-link self-enrollment with the agency as agent of record is a future, default-disabled option requiring carrier/state-specific approval and quality evidence.

**Competitive position:** auditable neutrality—reproducible, inspectable rankings independent of compensation, not “unbiased AI.” Target segments are caregivers first, self-directed researchers second, Medigap shoppers third. Distribution is direct caregiver content/search → financial-advisor software and publishers → health systems after outcome evidence. The 12–24 month incumbent-response window is a planning hypothesis; the assets to build are caregiver brand ownership, embedded integrations, self-serve conversion knowledge and published suitability/complaint/retention evidence. Serving people poorly served by phone-led research and scaling research capacity are the edge; licensed labor remains part of the service.

Start with [ARCHITECTURE.md](ARCHITECTURE.md). It covers the operating company, sourcing and carrier access, product capabilities, system boundaries, decision engines, advisor, consumer workspace, fulfillment, service, privacy, quality, finance and staged expansion.

Then read:

1. [DATABASE.md](DATABASE.md): actual CMS source observations, unknowns, acquisition dependencies and a minimal query-first data plan. **No final database schema is prescribed.**
2. [CONTRACTS.md](CONTRACTS.md): proposed module responsibilities and behavior shared by the consumer, advisor and execution system.
3. [BUILD_PLAN.md](BUILD_PLAN.md): concrete work packages, acceptance evidence, company dependencies and a Codex kickoff prompt.

## What grounds the data plan

Two actual public CMS archives were downloaded and inspected. The landscape CSV has 130,307 rows, 53 columns and 5,884 distinct year/contract/plan/segment combinations in that release. The PBP archive has 7,969 JSON members; five payloads were parsed. A candidate filename join exposes differences that still need explanation. Source hashes and descriptive profiles are in [evidence/](evidence/source-manifest.json).

These observations are not a complete ingestion or a validated insurance catalog. Formulary/pricing, provider/network, Medigap quote and enrollment payloads still need inspection and appropriate rights. The physical schema follows proven source meanings and queries, not the 25,000-options marketing premise.

## Saved prototype

The earlier exploratory code is [archived separately](../archived-prototype/README.md), with an [unchanged source ZIP](../prototype-code-snapshot.zip). Any old branding in that historical snapshot is a discarded placeholder. It is not the company name or the production specification.

## Review focus

- Is the intended product and company scope right?
- Are the caregiver-first segment order, auditable-neutrality claim, channel sequence and outcome-evidence plan explicit enough to execute and test?
- Do ranking transparency, licensed handoff, seasonal staffing and human-minute accounting implement the chosen operating model?
- Which real-data question and test market should the first slice prove?
- Which suppliers and operating relationships need samples/agreements first?
- Which proposed technology choices are useful now versus premature?
- What evidence will justify the first schema and the first consumer pilot?

This package defines a build approach and its dependencies; it does not claim completed production infrastructure, real quotes or an operational licensed-agent enrollment service. The archived prototype and original source evidence are historical artifacts; this revised architecture governs future implementation.
