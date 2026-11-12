# Directive history

Until November 5, 2026, owner directives were prepended as dated paragraphs to
the agent entry points. That made `AGENTS.md` 18,896 bytes and the advisor's
`AGENTS.md` 39,201 bytes, with current and superseded direction interleaved.

On November 5 the owner directed consolidating that history into one living
document ([CURRENT_STATE.md](CURRENT_STATE.md)) and moving dated history out of
the agent entry points. The two files below are **byte-exact copies** of the
entry points as they stood before that change. Nothing was paraphrased or
removed from them.

| Copy | Original path | Bytes | SHA-256 |
| --- | --- | --- | --- |
| [AGENTS.root.2026-11-05.md](directive-history/AGENTS.root.2026-11-05.md) | `AGENTS.md` | 18,896 | `1bd7d2cd40ed36bee02b6737d3a694992d53658ee110c82938de27287c218fac` |
| [AGENTS.advisor-first.2026-11-05.md](directive-history/AGENTS.advisor-first.2026-11-05.md) | `alternatives/advisor-first/AGENTS.md` | 39,201 | `c409d805d86807e9a0d40b6b25ff8de72116b969485acb8f8a1aec938e200600` |

## How to use this history

- Directives here remain binding where a later directive or
  [CURRENT_STATE.md](CURRENT_STATE.md) has not superseded them.
- Before changing an area, read its entries and the evidence packet each links.
- If the consolidated documents and a directive here disagree, treat it as an
  open question for the owner, not as permission to choose either one.

## New directives

Append below, newest last: date, decision ID, the owner's direction, and the
evidence link. Then update [CURRENT_STATE.md](CURRENT_STATE.md) in place.

| Date | ID | Direction | Evidence |
| --- | --- | --- | --- |
| 2026-11-05 | — | Consolidate governance: short `AGENTS.md` entry points, one living current-state document, dated history preserved here. | [Stack implementation record](STACK_IMPLEMENTATION_2026-11-05.md) |
| 2026-11-05 | D94 | Proceed with inventory, recovery-first exact deduplication and compact MVP storage preparation within existing local capacity. Preserve every source, critical inference, all 41 meanings, fourteen feature families, holds and exact-purpose gates; report actual space observations and remaining review. | [Storage maintenance](../reviews/storage-maintenance-2026-11-05/README.md) |
| 2026-11-05 | D94 | Proceed next with the database/index redesign within current space. Preserve every source and MVP feature; verify recovery before retiring anything. This extends the physical database scope while retaining source, privacy and purpose gates. | [Database/index redesign](../reviews/database-redesign-2026-11-05/README.md) |
| 2026-11-06 | D94 | Reconcile the dependency-lock mismatch while preserving sealed history and current dependency work; rerun verification and explain what remains for review. | [Dependency reconciliation](../reviews/dependency-reconciliation-2026-11-06/README.md) |
| 2026-11-06 | D95 | Evaluate the database against the AI-native brokerage plan and prepare transition actions. Cloud migration is expected soon; off-machine/PITR work is lower priority than AI-native database readiness. Preserve source/history/MVP and recovery-before-retirement; keep actual-target cutover checks. Evaluation does not authorize deployment or consumer release. | [Database readiness assessment](../reviews/ai-native-database-readiness-2026-11-06/README.md) |
| 2026-11-06 | D96 | Implement the backend plan for Collier PDP and Medigap data. No UI changes; keep consumer display gated until data approval, and report what is done and remains open. Preserve existing source/history/privacy boundaries; implementation does not supply data approval. | [Backend plan](../reviews/collier-plan-type-backend-2026-11-06/README.md) |
| 2026-11-07 | D98 | Draft the pilot scope amendment and budget/logging recommendations, and set up the development protections; bring concrete decisions for owner approval. Proposal drafting and SA-02 controls are authorized; scope exceptions, spending/retention changes, purchases and pilot release remain pending. | [Pilot security stage 1](../reviews/pilot-security-stage1-2026-11-07/README.md) |
