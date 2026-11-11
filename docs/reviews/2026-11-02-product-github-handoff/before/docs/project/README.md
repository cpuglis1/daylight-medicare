# Daylight project hub

**Repository controls now active · November 2, 2026:** [PR #1](https://github.com/cpuglis1/daylight-medicare/pull/1) publishes the first 12-file controls increment. Main requires pull requests and passing technical checks; maintenance belongs to @cpuglis1, with specialist roles pending. See [the operating guide](REPOSITORY_CHECKS.md) and [exact activation evidence](../reviews/2026-11-02-repository-controls/README.md). The full current advisor source/dependency handoff remains open; the original local working tree and its index are preserved.

Reviewed November 2, 2026, America/New_York. **Daylight has a substantial local advisor and research platform. It is not yet a released Medicare advice-and-enrollment service or a reproducible shared cloud environment.** The strongest progress is conversational education, structured reported profiles, retained source evidence and local data infrastructure. The critical unfinished work is accepted personal verification and comparison, operational recovery and permissions, qualified fulfillment, and observed consumer outcomes.

The owner confirmed **a 2026 controlled Collier County pilot first** and the existing [daylight-medicare GitHub repository](https://github.com/cpuglis1/daylight-medicare) as the code destination. The repository was verified public on November 2. The hosting account, region, service sizing, operating budget and deployment configuration remain undecided. The initial folder review prepared the handoff without publishing files, provisioning services or authorizing consumer recommendations. The subsequent repository-controls activation is recorded above.

## Start here

| Need | Current entrypoint |
| --- | --- |
| Understand what company we are building | [Company narrative and source map](../company/README.md) |
| Evaluate all fifteen company capabilities | [Capability assessment](CAPABILITIES.md) |
| Understand the 2026 Collier pilot and its gaps | [Pilot stages, backlog and release evidence](COLLIER_MVP.md) |
| Separate code, research evidence, databases and private state | [GitHub and cloud handoff](CLOUD_HANDOFF.md) |
| Work with other contributors safely | [Contributor workflow and ownership](CONTRIBUTING.md) |
| Inspect the folder review and its limits | [Review record](../reviews/2026-11-02-project-readiness/README.md) |
| Inspect the tested narrow developer handoff | [Isolated rehearsal and exact dependencies](../reviews/2026-11-02-project-readiness/DEVELOPER_REHEARSAL.md), [local ZIP](../../outputs/daylight-team-handoff-20261102/daylight-developer-rehearsal.zip) |
| Continue the already approved architecture work | [November 2 architecture and implementation guide](../planning/ARCHITECTURE_ALIGNMENT_AND_IMPLEMENTATION_2026-11-02.md) |

## Current implementation map

| Surface | Source and evidence | Meaning |
| --- | --- | --- |
| :8893 advisor-first | [Source/operations](../../alternatives/advisor-first/README.md), [scoped instructions](../../alternatives/advisor-first/AGENTS.md) | Current active advisor development: natural conversation, contextual teaching, report capture, correction, preparation and explicitly internal research/identity work. Local activation receipts exist; this review does not recertify the live process. |
| :8890 ten-question | [Contract](../product/TEN_QUESTION_CONTRACT.md), `cms-slice/apps/ten-question/` | Protected original ten-question journey and separate guest state. |
| :8891 chat-first | [Source/operations](../../alternatives/chat-first/README.md) | Protected alternative; canonical source here, separate sibling runtime outside this folder. Also supplies pinned engine dependencies used by :8893. |
| :8896 previous guide | `cms-slice/apps/chat/`, legacy server mode | Preserved prior guide, distinct from :8891. |
| Local research database/service | [Infrastructure](../../infrastructure/daylight-data/README.md), [persistent local runbook](../../infrastructure/daylight-data/runbooks/PERSISTENT_LOCAL.md) | All fifteen selected 2026 source-layer populations loaded locally; internal research bridge exists. Full domain models and accepted consumer serving remain unfinished. |
| Original Node prototype | [Original bundle](../../medicare-project-2026-10-17-v1.2/README.md) | Historical source, not the current application. |

The October 21 summaries in `docs/CURRENT_STATUS.md`, `docs/ARCHITECTURE.md`, `docs/DEVELOPMENT.md` and `docs/DATA_INVENTORY.md` remain dated records. They cannot describe the whole November 2 project. Likewise, newer data research does not inherit older exact acceptance.

## What the numbers mean

- The October 30 combined local load retained **17,767,179 source/context rows and 17,823,148 initial projections**, approximately **58.0 GB of PostgreSQL data at load completion**. These are research/storage counts, not verified benefits or accepted consumer findings. See [the load and query receipts](../data/infrastructure-execution-2026-10-30-local-full-db/).
- L03's frozen r9 contract covers **392,570 required claim/predicate obligations for 72 exact offerings**. Its accepted r4 reference remains **535 entries**. The [r12 whole-offering work](../data/l03-ma-benefits-2026-11-02-whole-offering-r12/README.md) continues a **4,675-obligation H5652-002 pilot** and remains unaccepted. These counts have different meanings and are not interchangeable completion denominators.
- The local folder occupied approximately **124 GiB as reported by `du -sh` during review**, including databases, archives, historical copies, Git objects and scratch space. This is not a proposed Git repository size or a count of unique source evidence.
- At the initial Git census, only **219 files were tracked**, against approximately **60,700 nonignored untracked files**. Counts change with concurrent work; [the inventory](../reviews/2026-11-02-project-readiness/inventory.json) records a bounded snapshot. A fresh GitHub clone does not reproduce this workspace.

## Organization applied

The project now has a single current navigation hub, a company identity map, a capability assessment, an MVP backlog, a contributor workflow and a storage/publication plan. Existing code, sealed packets and runtime stores remain at their original paths because hashes, manifests, imports and live services depend on them. This is a logical reorganization with executable inventory/preflight support, rather than an unverified directory move.

Future physical moves require an additive path map, source checksums, dependency updates and a clean-clone test. Acceptance records must continue to resolve their original identities and hashes. Moving a folder or restoring a database cannot promote evidence or merge guest permissions.
