# Documentation map

Current synthesis was checked against repository code and files on October 21, 2026. It does not renew source evidence or supply domain acceptance.

## Authority and current operating guides

1. [Product](../PRODUCT.md), [owner requirements](../DAYLIGHT_REQUIREMENTS.md), and [AGENTS](../AGENTS.md): binding direction and precedence.
2. [Current status and planning](CURRENT_STATUS.md): supported work, release limitations, and next decisions.
3. [Architecture](ARCHITECTURE.md), [development](DEVELOPMENT.md), and [data inventory](DATA_INVENTORY.md): current implementation and its evidence boundaries.
4. [Data acceptance standard](DATA_VALIDATION_ACCEPTANCE.md), [validated operations](VALIDATED_DATA_OPERATIONS.md), [exact-release review packet](../cms-slice/reports/collier-gap-20261020/validation/REVIEW_PACKET.md): source/reviewer/consumer gates.
5. [Collier execution checklist](../COLLIER_DATA_GAP_PLAN_current.md) and [owner review queue](../COLLIER_OWNER_REVIEW_REQUIRED.md): detailed C/H/O IDs. Keep holds and the collector STOP intact.
6. [One-page objectives PDF](planning/collier-mvp-2026-10-21/collier-mvp-plan.pdf), [HTML](planning/collier-mvp-2026-10-21/collier-mvp-plan.html), and [text](planning/collier-mvp-2026-10-21/plan-text.txt): the compact forward plan.
7. [Organization/rollback](REPOSITORY_ORGANIZATION.md), [Git readiness](GIT_READINESS.md), and [October 21 review](reviews/2026-10-21/REVIEW.md).

## Active UI guidance and review history

- [Learning flow](DAYLIGHT_LEARNING_FLOW.md): progressive teaching and contextual help.
- [65+ finish plan](DAYLIGHT_65_PLUS_FINISH_PLAN.md): approved finishing scope; participant acceptance still needs actual sessions.
- [UI flow](UI_FLOW.md): implementation-era map, subject to current requirements.
- [Prior user walkthrough](../audit-evidence/USER_WALKTHROUGH_2026-10-20.md), [flow review](../audit-evidence/FLOW_REVIEW_2026-10-20.md), and [fix record](../audit-evidence/FLOW_FIXES_2026-10-20.md): dated engineering evidence.
- [Archived UI proposals](archive/product-history/README.md): original teaching inventories and successive proposals, with precedence explained. All content is preserved.

## Specialized implementation and evidence

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
