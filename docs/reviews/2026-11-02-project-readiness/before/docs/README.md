# Documentation map

**Current post-summary UI:** [D71 optional conversational readiness](product/READINESS_CONVERSATION.md), installed locally October 22, 2026. D69 design previews below are retained research history, not the current interaction.

Current synthesis was checked against repository code and files on October 21, 2026. It does not renew source evidence or supply domain acceptance.

## Authority and current operating guides

**Architecture assessment and implementation guide · November 2, 2026:** [Alignment with the proposed conversational brokerage architecture](planning/ARCHITECTURE_ALIGNMENT_AND_IMPLEMENTATION_2026-11-02.md). Maps sixteen practices to current code/plans, identifies the confirmed-input, evidence-authority, recommendation, explanation, audit and enrollment gaps, and gives sixteen implementation steps with dependencies, owners and exit evidence. Assessment/planning only; existing requirements, permissions and exact-release gates remain in force. The October 21 architecture overview is retained as a dated snapshot.

**Canonical strategy · D73 · October 25, 2026:** [Strategic thesis and evidence roadmap](product/STRATEGIC_THESIS.md), including the UI/system review checklist, protected local variants and cohort measure definitions. It separates principles, hypotheses, current implementation and gated milestones; older scoped execution plans below remain supporting material, not competing strategic masters.

**Scale and data-quality thesis · October 29, 2026:** [Scale folder](scale/README.md) and [15-layer scalability/competitive-advantage guide](scale/GUIDE.md). Covers Florida/national reuse, source pipelines, APIs and optional feeds, hard-layer verification and evidence needed to prove an advantage. Strategic analysis, not national coverage or release acceptance.

**Central product ambition · D73 · October 30, 2026:** [Tell Daylight what is happening in your life](product/STRATEGIC_THESIS.md#central-product-ambition). Make education, self-discovery and supported research easier; depth must produce consumer value, including when the selected plan stays the same. First-transition independent researchers are the starting audience to test. Separate directed LLM conversation versus an excellent adaptive form on the same evidence from basic/richer evidence through the same interface. High-level ambition and open hypotheses, not a new flow specification or release claim.

**Conversation research · October 30, 2026:** [Five studies, findings and limits](product/STRATEGIC_THESIS.md#evidence-for-conversation-and-its-limits), with the audience hypothesis focused on difficulty translating life circumstances into Medicare categories. The evidence supports testing, not an established advantage over an excellent adaptive Medicare form. [Dated strategy copy — October 30, 2026](product/STRATEGIC_THESIS_2026-10-30.md); the undated file remains canonical.

**Hybrid study condition · October 30, 2026:** [Three interface conditions](product/STRATEGIC_THESIS.md#three-interface-conditions): excellent adaptive form, directed textual LLM conversation and conversation with inline mini-forms. Review follows form submission; explicit confirmation precedes the named action. Match evidence, tools and review/confirmation standards across conditions. The separate evidence-depth experiment remains; today's dated copy includes the addition.

1. [Product](../PRODUCT.md), [owner requirements](../DAYLIGHT_REQUIREMENTS.md), and [AGENTS](../AGENTS.md): binding direction and precedence.
2. [Current status and planning](CURRENT_STATUS.md): supported work, release limitations, and next decisions.
3. [Architecture](ARCHITECTURE.md), [development](DEVELOPMENT.md), and [data inventory](DATA_INVENTORY.md): current implementation and its evidence boundaries.
4. [Data acceptance standard](DATA_VALIDATION_ACCEPTANCE.md), [validated operations](VALIDATED_DATA_OPERATIONS.md), [exact-release review packet](../cms-slice/reports/collier-gap-20261020/validation/REVIEW_PACKET.md): source/reviewer/consumer gates.
5. [Collier execution checklist](../COLLIER_DATA_GAP_PLAN_current.md) and [owner review queue](../COLLIER_OWNER_REVIEW_REQUIRED.md): detailed C/H/O IDs. Keep holds and the collector STOP intact.
6. [One-page objectives PDF](planning/collier-mvp-2026-10-21/collier-mvp-plan.pdf), [HTML](planning/collier-mvp-2026-10-21/collier-mvp-plan.html), and [text](planning/collier-mvp-2026-10-21/plan-text.txt): the compact forward plan.
7. [Organization/rollback](REPOSITORY_ORGANIZATION.md), [Git readiness](GIT_READINESS.md), and [October 21 review](reviews/2026-10-21/REVIEW.md).

## Active UI guidance and review history

- [Master design and agent contract](product/MASTER_DESIGN.md): latest agent-first target, guest-profile architecture and precedence; includes [branching nodes](product/BRANCHING_NODES.md), [wireframes](product/WIREFRAMES.md), [JSON contract](product/flow-contract.json), and [acceptance/handoff](product/ACCEPTANCE_AND_HANDOFF.md). Documentation-only specification; it does not claim implementation.

- [Prior learning flow](DAYLIGHT_LEARNING_FLOW.md): reusable progressive teaching; latest goal/knowledge/agent/persistence decisions are in the master.
- [65+ finish plan](DAYLIGHT_65_PLUS_FINISH_PLAN.md): approved finishing scope; participant acceptance still needs actual sessions.
- [UI flow](UI_FLOW.md): implementation-era map, subject to current requirements.
- [Prior user walkthrough](../audit-evidence/USER_WALKTHROUGH_2026-10-20.md), [flow review](../audit-evidence/FLOW_REVIEW_2026-10-20.md), and [fix record](../audit-evidence/FLOW_FIXES_2026-10-20.md): dated engineering evidence.
- [Archived UI proposals](archive/product-history/README.md): original teaching inventories and successive proposals, with precedence explained. All content is preserved.

## Specialized implementation and evidence

**L14 · October 29, 2026:** [Other coverage paths reference and genuine gaps](data/l14-other-coverage-2026-10-29/REPORT.md), [field validation](data/l14-other-coverage-2026-10-29/VALIDATION.md) and [R19 review packet](data/l14-other-coverage-2026-10-29/REVIEW.md). Published dated PACE/Cost/MSA/HCPP/LI NET research; full L14 and consumer acceptance remain partial/held.

| Topic | Sources retained in place |
| --- | --- |
| Data acquisition and test-market findings | [WP1](WORK_PACKAGE_1.md), [WP2](WORK_PACKAGE_2.md), [WP3](WORK_PACKAGE_3.md), [Naples data](NAPLES_DATA.md), [slice guide](../cms-slice/README.md), [validation record](../cms-slice/VALIDATION.md) |
| Service/catalog/model history | [Naples MVP](NAPLES_MVP.md), [Milkman implementation](MILKMAN_CHAT_IMPLEMENTATION.md), [Milkman review](MILKMAN_CHAT_REVIEW.md), [ZIP demo plan](ZIP_34102_DEMO_PLAN.md) |
| Source collection | [Collector operations and STOP](MEDICARE_COLLECTOR.md) |
| Original architecture and broad product contract | [Architecture review](ARCHITECTURE_REVIEW.md), [product workflow](PRODUCT_WORKFLOW.md), [persistence proposal](PERSISTENCE_PROPOSAL.md), [action reference](../ACTION_REFERENCE.md), [plan of attack](../PLAN_OF_ATTACK.md) |
| Historical progress reports | [Completion report](COMPLETION_REPORT.md), [execution ledger](EXECUTION_STATUS.md), [demo execution](DEMO_EXECUTION.md), [demo handoff](DEMO_HANDOFF.md) |
| Earlier audits and test protocol | [Initial audit](NAPLES_DEMO_AUDIT.md), [re-audit](NAPLES_DEMO_REAUDIT.md), [research protocol](RESEARCH_REVIEW_PROTOCOL.md) |
| Original data-layer assessment | [Collier inventory](../Collier%20County%20Medicare%20Data%20Inventory.md), [older gap plan](COLLIER_DATA_GAP_PLAN.md), [audit outputs](../outputs/daylight-audit-20261019/) |
| Other retained artifacts | [Historical implementation prompt](milkman_implementation_prompt.md), [original v1.2 bundle](../medicare-project-2026-10-17-v1.2/README.md) |

## How to reconcile conflicting statements

Use latest explicit owner direction first, then numbered requirements and product precedence. Use current code, source hashes, and exact-release records for implementation facts. A dated completion claim, old test count, original Data Layers workbook, or successful capture is not consumer acceptance. The newer data synthesis supersedes old statements that ratings are absent, only 31 networks are packaged, or only 38 records can be represented by the catalog. The original records remain unchanged for provenance.

Evidence directories and original package internals stay in place because scripts, manifests, or historical receipts consume their paths. This index provides navigation without a risky wholesale migration.

Approved visual implementation reference: [root DESIGN.md](../DESIGN.md), D58–D59; flow/state authority remains [the master package](product/MASTER_DESIGN.md).

## Planned readiness check (D69, design only)

[Main contract](product/READINESS_DESIGN.md) · [Trigger questions and edge cases](product/READINESS_TRIGGERS.md) · [Dated primary sources](product/READINESS_SOURCES.md) · [Acceptance scenarios](product/READINESS_ACCEPTANCE.md) · [Isolated wireframe](product/readiness-preview/index.html). This proposal follows the ten-question summary; the current app is unchanged and personalized matching remains held.
