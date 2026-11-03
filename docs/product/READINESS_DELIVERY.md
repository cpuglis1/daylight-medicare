# Readiness-check design delivery

October 22, 2026 · D69 design/research only · **Not live integration or licensed validation.**

## Delivered

[Interactive local preview](http://127.0.0.1:8898/readiness-preview/) · [captured desktop/phone screens](readiness-preview/review.html) · [design contract](READINESS_DESIGN.md) · [trigger matrix](READINESS_TRIGGERS.md) · [dated official sources](READINESS_SOURCES.md) · [acceptance scenarios](READINESS_ACCEPTANCE.md) · [machine-readable research inventory](readiness-triggers.json).

The proposed position is ten-question summary confirmation → capability/source preflight → zero or more targeted details → readiness by capability → supported options or an explicit held boundary. There are **30 stable research trigger entries and 29 official source notes**, not 30 mandatory intake questions. System guards and final application confirmation are separate from patient follow-ups. The finite queue contract deduplicates, respects dependencies, remembers unknown/deferred answers and requires explicit reopening. The proposed six-primary-prompt pass limit is a product burden guard for review, not an insurance rule or promise of completeness.

The contextual introduction is “A few details can change which coverage fits. Let’s check what matters for you.” Every follow-up has one brief specific Why we ask line. Detailed rationale and sources live in optional help/specification. No new homepage slogan.

## Research findings requiring careful implementation

A/B enrollment, MA/PDP elections, creditable-drug gaps and Medigap purchase rights use distinct facts and clocks. Current work differs from COBRA/retiree coverage; payer-order headcount paths depend on eligibility basis and exceptions. Requested start month is not actual enrollment or eligibility. Florida statutory Medigap opportunities must be reviewed separately from federal examples; no blanket guarantee of issueability or absence of underwriting. Provider/RxNorm identity is not network/formulary evidence. Cost preference is not affordability or a verified total. 2026 rules/amounts cannot silently establish a 2027 quote. See the exact source sections, dates, jurisdiction and interpretation flags in the source notes and matrix.

The ten fields do not establish full official Medicare eligibility, quote readiness or all current-coverage consequences. An official eligibility check may require facts such as lawful residence and premium-free Part A qualification that are not collected here; the draft does not authorize collecting sensitive proof documents or government identifiers. Neither the LLM nor this wireframe decides eligibility. Human confirmation is a report, not independent verification.

## Measured prototype checks

Command: `node --test docs/product/readiness-preview/model.test.cjs` — **13 passed, 0 failed**. JavaScript syntax checks passed. Tests cover finite/deduplicated queues, zero-gap completion, unknown/defer dependencies, all-unknown termination, Back without duplicate frames, pass limit, Finish, fixture termination, registry/source references, acyclic dependencies, preserved rechecks and stale-proposal guards. They exercise the synthetic interaction model, not implemented legal predicates.

Actual browser observations in the ChatGPT in-app browser:

- Desktop 1440×1000 and phone 390×844: entry, question, scripted proposal, Ask overlay and capability summary captured. Tablet 768×1024: summary captured. Question/summary phone and tablet summary had no horizontal overflow.
- Job-coverage fixture: RC09 → RC11 → RC12 → terminal summary. Three displayed primary details; no topic loop. The complete-facts fixture reached summary with **zero follow-up questions**.
- All three missing-baseline details deferred → terminal summary with three open items. Deferring the job parent blocked dependent details without automatically asking them.
- Explicitly reopening and resolving deferred RC09 retained the other two open details as Ready for review. Separate model regression preserves unrelated confirmed reports, drafts and deferrals after affected-answer review.
- Free-text input is retained through Back. A scripted proposal requires confirmation; changing its wording removes the stale proposal and Use action. Confirm is tied to the current node/current exact text. Proposal heading receives focus and is revealed; the competing structured Continue is hidden during valid proposal confirmation.
- Ask Escape restores launcher focus/current question. Drafts remain in this tab; the underlying task does not reflow. Unavailable AI leaves manual controls usable and free text unresolved. No model or paid request ran.
- Explicit edit/save returns to summary with dependent-review notice. No new coverage answer is preselected. The sample boundary keeps plan-data/eligibility claims held.

A fresh Impeccable finish reviewer first found state-loss, stale-proposal and proposal-focus/action issues. One correction batch addressed them; the same reviewer scored all three resolved and returned **“Ship as an isolated design wireframe.”** This verdict covers the listed artifact interactions, not clinical/legal validity, matching, live integration, accessibility certification or owner approval. Detector ran once; mechanical font-alias/overlay-color issues were corrected. Owner-pinned palette/fonts were retained. A fresh Impeccable documenter compared the finished preview to the incumbent system and recommended leaving root DESIGN.md and its sidecar unchanged. Prototype type-ramp advisories are documented for future integration mapping.

Not verified: screen-reader speech, real mobile keyboards, low-vision zoom/reflow at all scales, older-adult/cognitive comprehension, live model/extraction, source refresh adapters, production predicate engine, actual guest persistence/concurrency/delete for new readiness facts, plan/network/drug/pricing services or final enrollment. Their required scenarios are specified, not falsely marked passed.

## Preservation and boundaries

This task wrote only new readiness design/preview files and minimal documentation navigation/authority pointers in PRODUCT.md, DAYLIGHT_REQUIREMENTS.md, MASTER_DESIGN.md, TEN_QUESTION_CONTRACT.md and docs/README.md. The live ten-question app, source datasets, guest records, credentials and shared $1/UTC-day budget implementation were not edited by this task. A separate owner-authorized ingestion thread is concurrently applying live wording corrections; those changes are independent and must not be reverted by this package.

Before-images: [documentation entry points](history/2026-10-22-before-readiness-spec/) and [first preview before review fixes](history/2026-10-22-before-readiness-finish-review/). Existing brand/system files are preserved; no commit, push or deployment. The preview binds loopback only on port 8898, calls no model/API and writes no storage. Refresh resets fictional state; this is intentionally not a persistence demonstration.

## Before integration

Owner review of burden/copy; qualified federal/Florida Medicare rule review; approved typed predicates/source receipts/versioning; consented companion-record schema and privacy/retention review; then pure-engine fixtures and profile/UI adapters behind a local feature boundary. The current schema-v2 guest envelope must not silently receive unapproved fields or migrate. Sources/plan-year/county/category validation, provider/drug/pricing integration, independent recommendation evaluations and final application confirmation remain separate prerequisites. Readiness completion alone does not unlock matching or make an incomplete catalog comprehensive.
